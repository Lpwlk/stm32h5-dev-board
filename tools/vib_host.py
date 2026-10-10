#!/usr/bin/env python3
"""Host side of the vibration board: packet format, simulator, receiver, viewer.

Lets you build and test the PC pipeline before the hardware exists, and defines
the wire format the firmware should implement. The same record format is used for
UDP packets and for log files on the SD card (a log is just packets back to back),
so one parser reads both.

Packet (little endian), 20 byte header + int16 samples interleaved by channel:
    magic    2s   b"VB"
    version  u8   1
    sensor   u8   sensor id (0 = IIS3DWB, 1 = IMU, ...)
    seq      u32  per-sensor packet counter (loss detection)
    t0_us    u64  timestamp of the first sample (device timer / PTP time)
    n        u16  samples per channel in this packet
    channels u8
    fmt      u8   0 = int16

Commands:
  sim   [--host H --port P --fs HZ]       send synthetic data (no hardware needed)
  rx    [--port P --fs HZ --range G --log F.vib --plot]   receive, report loss, optionally log/plot
  read  FILE.vib [--csv out.csv] [--plot]  decode a log file (e.g. copied off the SD card)

Needs only the stdlib, except --plot which needs numpy + matplotlib.
"""
from __future__ import annotations

import argparse
import math
import random
import socket
import struct
import sys
import time
from dataclasses import dataclass

HDR = struct.Struct("<2sBBIQHBB")
MAGIC = b"VB"
LSB_G = {2: 0.061e-3, 4: 0.122e-3, 8: 0.244e-3, 16: 0.488e-3}  # IIS3DWB sensitivity, g/LSB


@dataclass
class Packet:
    sensor: int
    seq: int
    t0_us: int
    channels: int
    samples: list[int]  # interleaved int16

    @property
    def n(self) -> int:
        return len(self.samples) // self.channels


def encode(p: Packet) -> bytes:
    return HDR.pack(MAGIC, 1, p.sensor, p.seq, p.t0_us, p.n, p.channels, 0) + struct.pack(f"<{len(p.samples)}h", *p.samples)


def decode(buf: bytes, off: int = 0) -> tuple[Packet, int]:
    magic, ver, sensor, seq, t0, n, ch, fmt = HDR.unpack_from(buf, off)
    if magic != MAGIC or ver != 1 or fmt != 0:
        raise ValueError(f"bad header at offset {off}: {magic!r} v{ver} fmt{fmt}")
    cnt = n * ch
    end = off + HDR.size + cnt * 2
    if end > len(buf):
        raise ValueError("truncated packet")
    samples = list(struct.unpack_from(f"<{cnt}h", buf, off + HDR.size))
    return Packet(sensor, seq, t0, ch, samples), end


def iter_log(data: bytes):
    off = 0
    while off + HDR.size <= len(data):
        try:
            p, off = decode(data, off)
        except ValueError as e:
            print(f"log ends/corrupt: {e}", file=sys.stderr)
            return
        yield p


class LossTracker:
    def __init__(self):
        self.last: dict[int, int] = {}
        self.received = 0
        self.lost = 0

    def update(self, p: Packet):
        self.received += 1
        prev = self.last.get(p.sensor)
        if prev is not None:
            gap = (p.seq - prev - 1) & 0xFFFFFFFF
            if gap < 1 << 31:
                self.lost += gap
        self.last[p.sensor] = p.seq


def cmd_sim(a) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    n = a.samples
    t = 0
    seq = 0
    period = n / a.fs
    start = time.monotonic()
    print(f"sending {a.fs:.0f} Hz x3ch, {n} samples/packet -> {a.host}:{a.port} (Ctrl-C to stop)")
    try:
        while True:
            s = []
            for i in range(n):
                tt = (t + i) / a.fs
                # 1 kHz tone on X, 2.4 kHz (bearing-like) on Y with an amplitude wobble, gravity on Z
                x = 0.5 * math.sin(2 * math.pi * 1000 * tt) + random.gauss(0, 0.01)
                y = 0.2 * (1 + 0.5 * math.sin(2 * math.pi * 3 * tt)) * math.sin(2 * math.pi * 2400 * tt) + random.gauss(0, 0.01)
                z = 1.0 + random.gauss(0, 0.01)
                s += [int(v / LSB_G[a.range]) for v in (x, y, z)]
            if random.random() >= a.drop:
                sock.sendto(encode(Packet(0, seq, int(t / a.fs * 1e6), 3, s)), (a.host, a.port))
            seq += 1
            t += n
            delay = start + seq * period - time.monotonic()
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        return 0


def spectrum_plot(samples_by_ch, fs, title):
    import numpy as np
    import matplotlib.pyplot as plt

    fig, (ax_t, ax_f) = plt.subplots(2, 1, figsize=(10, 6))
    n = min(len(c) for c in samples_by_ch)
    t = np.arange(n) / fs
    win = np.hanning(n)
    freqs = np.fft.rfftfreq(n, 1 / fs)
    for i, c in enumerate(samples_by_ch):
        c = np.asarray(c[:n], dtype=float)
        ax_t.plot(t, c, label="xyz"[i] if i < 3 else f"ch{i}", lw=0.7)
        mag = np.abs(np.fft.rfft((c - c.mean()) * win)) * 2 / win.sum()
        ax_f.semilogy(freqs, mag + 1e-9, lw=0.7)
    ax_t.set(title=title, xlabel="time [s]", ylabel="acceleration [g]")
    ax_t.legend(loc="upper right")
    ax_f.set(xlabel="frequency [Hz]", ylabel="amplitude [g]", xlim=(0, fs / 2))
    fig.tight_layout()
    return plt


def to_channels(pkts: list[Packet], lsb: float):
    ch = pkts[0].channels
    out = [[] for _ in range(ch)]
    for p in pkts:
        for i in range(ch):
            out[i].extend(v * lsb for v in p.samples[i::ch])
    return out


def cmd_rx(a) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
    sock.bind(("0.0.0.0", a.port))
    sock.settimeout(1.0)
    lsb = LSB_G[a.range]
    loss = LossTracker()
    log = open(a.log, "wb") if a.log else None
    window: list[Packet] = []
    need = int(a.fs * a.window)
    t_report = time.monotonic()
    nbytes = 0
    print(f"listening on UDP :{a.port}  (Ctrl-C to stop)")
    try:
        while True:
            try:
                buf, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            try:
                p, _ = decode(buf)
            except ValueError as e:
                print("bad packet:", e, file=sys.stderr)
                continue
            nbytes += len(buf)
            loss.update(p)
            if log:
                log.write(buf)
            if p.sensor != a.sensor:
                continue
            window.append(p)
            if sum(q.n for q in window) >= need:
                if a.plot:
                    plt = spectrum_plot(to_channels(window, lsb), a.fs, f"sensor {a.sensor}")
                    plt.show()
                    return 0
                window.clear()
            now = time.monotonic()
            if now - t_report >= 1.0:
                print(f"{nbytes * 8 / (now - t_report) / 1e6:6.2f} Mbit/s  packets {loss.received}  lost {loss.lost}")
                t_report, nbytes = now, 0
    except KeyboardInterrupt:
        return 0
    finally:
        if log:
            log.close()


def cmd_read(a) -> int:
    data = open(a.file, "rb").read()
    pkts = list(iter_log(data))
    if not pkts:
        print("no packets decoded")
        return 1
    loss = LossTracker()
    for p in pkts:
        loss.update(p)
    span = (pkts[-1].t0_us - pkts[0].t0_us) / 1e6
    print(f"{len(pkts)} packets, {sum(p.n for p in pkts)} samples/channel, {span:.2f} s, lost {loss.lost}")
    sel = [p for p in pkts if p.sensor == a.sensor]
    lsb = LSB_G[a.range]
    if a.csv:
        with open(a.csv, "w") as fh:
            fh.write("t_s,x_g,y_g,z_g\n")
            for p in sel:
                for i in range(p.n):
                    t = p.t0_us / 1e6 + i / a.fs
                    v = p.samples[i * p.channels:(i + 1) * p.channels]
                    fh.write(f"{t:.6f}," + ",".join(f"{x * lsb:.5f}" for x in v) + "\n")
        print("wrote", a.csv)
    if a.plot and sel:
        spectrum_plot(to_channels(sel, lsb), a.fs, a.file).show()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--fs", type=float, default=26667.0, help="sample rate in Hz (IIS3DWB: 26667)")
        p.add_argument("--range", type=int, choices=sorted(LSB_G), default=16, help="full scale in g")

    s = sub.add_parser("sim")
    common(s)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=5005)
    s.add_argument("--samples", type=int, default=200, help="samples per channel per packet")
    s.add_argument("--drop", type=float, default=0.0, help="probability of dropping a packet")
    s.set_defaults(fn=cmd_sim)

    r = sub.add_parser("rx")
    common(r)
    r.add_argument("--port", type=int, default=5005)
    r.add_argument("--sensor", type=int, default=0)
    r.add_argument("--log", help="also write raw packets to this .vib file")
    r.add_argument("--plot", action="store_true", help="capture --window seconds then show time + spectrum")
    r.add_argument("--window", type=float, default=0.5)
    r.set_defaults(fn=cmd_rx)

    d = sub.add_parser("read")
    common(d)
    d.add_argument("file")
    d.add_argument("--sensor", type=int, default=0)
    d.add_argument("--csv")
    d.add_argument("--plot", action="store_true")
    d.set_defaults(fn=cmd_read)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
