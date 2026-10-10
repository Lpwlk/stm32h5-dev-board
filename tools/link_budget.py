#!/usr/bin/env python3
"""Data-rate budget: does the sensor stream fit the link, and at what latency?

Compares USB full-speed, 10BASE-T1S, 100BASE-TX and a microSD card for a given
set of streams, including per-frame protocol overhead.

Examples:
  link_budget.py                                   # 1x IIS3DWB, 26.667 kHz, 3 axes, 16 bit
  link_budget.py -s 26667:3:2 -s 26667:3:2         # two IIS3DWB
  link_budget.py -s 26667:3:2 -a 1000000:2:2       # + 2-channel ADC at 1 MSPS
  link_budget.py -s 26667:3:2 --packet-bytes 256   # lower latency, more overhead

Stream spec is  SAMPLE_RATE_HZ:CHANNELS:BYTES_PER_SAMPLE.
Link efficiency numbers are theoretical best cases for bulk, in-order traffic.
Real USB/SD throughput is lower; treat anything above ~60% as at risk.
"""
from __future__ import annotations

import argparse
import sys

APP_HDR = 20  # bytes of our own header per packet (see vib_host.py)


def parse_stream(txt: str) -> tuple[float, int, int]:
    try:
        rate, ch, size = txt.split(":")
        return float(rate), int(ch), int(size)
    except ValueError:
        raise argparse.ArgumentTypeError("expected RATE:CHANNELS:BYTES, e.g. 26667:3:2")


def udp_wire_bytes(payload: int) -> int:
    # UDP 8 + IPv4 20 + Ethernet 14 + FCS 4 + preamble/SFD 8 + IFG 12; min frame 64 (+20)
    frame = max(payload + 8 + 20 + 14 + 4, 64)
    return frame + 8 + 12


def t1s_wire_bytes(payload: int) -> int:
    # 10BASE-T1S frame: same Ethernet framing as above; PLCA beacon/commit costs ignored.
    return udp_wire_bytes(payload)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--stream", action="append", type=parse_stream, default=[],
                    help="digital sensor stream RATE:CH:BYTES (repeatable)")
    ap.add_argument("-a", "--adc", action="append", type=parse_stream, default=[],
                    help="ADC stream RATE:CH:BYTES (repeatable)")
    ap.add_argument("--packet-bytes", type=int, default=1200,
                    help="application payload per packet incl. our header (default 1200)")
    ap.add_argument("--nodes", type=int, default=1,
                    help="boards sharing the medium (matters for T1S multidrop)")
    a = ap.parse_args()

    streams = a.stream + a.adc or [(26667.0, 3, 2)]
    payload_rate = sum(r * c * b for r, c, b in streams)  # bytes/s from sensors
    data_per_packet = max(a.packet_bytes - APP_HDR, 1)
    pkt_rate = payload_rate / data_per_packet
    latency_ms = data_per_packet / payload_rate * 1e3

    print(f"Sensor payload      : {payload_rate / 1e3:10.1f} kB/s  = {payload_rate * 8 / 1e6:.2f} Mbit/s")
    print(f"Packet              : {a.packet_bytes} B -> {pkt_rate:.0f} packets/s, "
          f"batching latency {latency_ms:.2f} ms\n")

    # (name, capacity in bytes/s on the wire, wire bytes for one packet)
    links = [
        ("USB 2.0 FS (bulk)", 1.216e6,  # 19 x 64 B bulk packets per 1 ms frame
          a.packet_bytes),
        ("10BASE-T1S", 10e6 / 8, t1s_wire_bytes(a.packet_bytes)),
        ("100BASE-TX UDP", 100e6 / 8, udp_wire_bytes(a.packet_bytes)),
    ]
    print(f"{'link':20s} {'capacity':>12s} {'load':>12s} {'util':>7s}  verdict")
    for name, cap, wire in links:
        load = pkt_rate * wire
        if name.startswith("10BASE-T1S") and a.nodes > 1:
            cap = cap / a.nodes  # fair PLCA share, optimistic
            name += f" /{a.nodes}"
        util = load / cap
        verdict = "ok" if util < 0.6 else "tight" if util < 0.9 else "NO"
        print(f"{name:20s} {cap / 1e6:9.2f} MB/s {load / 1e6:9.3f} MB/s {util * 100:6.1f}%  {verdict}")

    sd_cap = 10e6  # conservative sustained FATFS multi-block write on a decent A1/V30 card
    util = payload_rate / sd_cap
    need_buf = payload_rate * 0.25  # card write stalls of 100-250 ms are routine
    print(f"{'microSD 4-bit':20s} {sd_cap / 1e6:9.2f} MB/s {payload_rate / 1e6:9.3f} MB/s "
          f"{util * 100:6.1f}%  {'ok' if util < 0.6 else 'tight' if util < 0.9 else 'NO'}"
          f"   (buffer >= {need_buf / 1024:.0f} KiB to ride out 250 ms write stalls)")
    print("\nNotes: USB row is payload only (no per-packet framing model); the H5 has full-speed USB only.")
    print("       The T1S row assumes the whole medium is yours; PLCA splits it among nodes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
