#!/usr/bin/env python3
"""STM32 pin planner / checker backed by the STM32CubeMX MCU database.

The CubeMX install already ships an authoritative XML file per part
(db/mcu/<RefName>.xml) listing, for every physical pin, which signals it can
carry. This tool uses it so pin allocation is checked against real data instead
of memory.

Usage:
  pinplan.py query  ETH_             # which pins can carry ETH_* signals
  pinplan.py query  'SPI[1-6]_(SCK|MISO|MOSI)' --mcu STM32H563VITx
  pinplan.py check  pinplan.toml     # validate a plan (exit 1 on errors)
  pinplan.py table  pinplan.toml     # markdown table for the HW spec
  pinplan.py free   pinplan.toml     # unused GPIOs, grouped by port

Set STM32_MCU_DB to override the database directory.
Pure stdlib; needs Python >= 3.11 (tomllib).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

NS = {"m": "http://mcd.rou.st.com/modules.php?name=mcu"}
DB_CANDIDATES = [
    "/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/db/mcu",
    "~/STM32CubeMX/db/mcu",
    "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/db/mcu",
]
DEFAULT_MCU = "STM32H563VITx"
# Pins with a hardware meaning at reset; using them is legal but flagged.
SPECIAL = {
    "PA13": "SWDIO (debug)",
    "PA14": "SWCLK (debug)",
    "PH0": "HSE OSC_IN",
    "PH1": "HSE OSC_OUT",
    "PC14": "LSE OSC32_IN",
    "PC15": "LSE OSC32_OUT",
    "PA15": "JTDI after reset",
    "PB3": "SWO / JTDO after reset",
    "PB4": "NJTRST after reset",
}


class Pin:
    def __init__(self, name: str, position: str, ptype: str, signals: list[str]):
        # DB names look like "PH0-OSC_IN(PH0)"; keep the GPIO name.
        self.name = re.split(r"[-(]", name)[0]
        self.position = position
        self.type = ptype
        self.signals = set(signals)

    @property
    def is_gpio(self) -> bool:
        return self.type == "I/O" and re.fullmatch(r"P[A-K]\d+", self.name) is not None


def find_db() -> Path:
    env = os.environ.get("STM32_MCU_DB")
    for c in ([env] if env else []) + DB_CANDIDATES:
        p = Path(c).expanduser()
        if p.is_dir():
            return p
    sys.exit("MCU database not found. Install STM32CubeMX or set STM32_MCU_DB.")


def load_mcu(ref: str) -> dict[str, Pin]:
    f = find_db() / f"{ref}.xml"
    if not f.exists():
        close = sorted(p.stem for p in f.parent.glob(f"{ref[:9]}*.xml"))[:10]
        sys.exit(f"{f.name} not found in DB. Similar parts: {', '.join(close) or 'none'}")
    root = ET.parse(f).getroot()
    pins = {}
    for p in root.findall("m:Pin", NS):
        sigs = [s.get("Name") for s in p.findall("m:Signal", NS)]
        pin = Pin(p.get("Name"), p.get("Position"), p.get("Type"), sigs)
        pins[pin.name if pin.is_gpio else f"{pin.name}@{pin.position}"] = pin
    return pins


def cmd_query(a) -> int:
    pins = load_mcu(a.mcu)
    rx = re.compile(a.pattern)
    hits = defaultdict(list)
    for pin in pins.values():
        for s in sorted(pin.signals):
            if rx.search(s):
                hits[s].append(f"{pin.name}({pin.position})")
    for s in sorted(hits):
        print(f"{s:24s} {' '.join(hits[s])}")
    if not hits:
        print("no match", file=sys.stderr)
        return 1
    return 0


def load_plan(path: str):
    with open(path, "rb") as fh:
        plan = tomllib.load(fh)
    return plan.get("mcu", DEFAULT_MCU), plan.get("pin", []), plan.get("reserve", [])


def cmd_check(a) -> int:
    mcu, entries, reserved = load_plan(a.plan)
    pins = load_mcu(mcu)
    errors, warns = [], []
    used: dict[str, dict] = {}
    for e in entries:
        pin, sig = e.get("pin"), e.get("signal")
        if pin not in pins:
            errors.append(f"{pin}: not a GPIO on {mcu}")
            continue
        if pin in used:
            errors.append(f"{pin}: used twice ({used[pin]['signal']} and {sig})")
            continue
        used[pin] = e
        if sig not in ("GPIO", "GPIO_IN", "GPIO_OUT", "GPIO_EXTI") and sig not in pins[pin].signals:
            alts = sorted(p for p, v in pins.items() if v.is_gpio and sig in v.signals)
            errors.append(f"{pin}: cannot carry {sig}. {sig} is available on: {', '.join(alts) or 'nowhere'}")
        if pin in SPECIAL and not e.get("allow_special"):
            warns.append(f"{pin}: {SPECIAL[pin]} — set allow_special=true if intentional")
    # a peripheral instance spread across several SPI/SDMMC groups is fine,
    # but one signal on two pins is a mistake
    per_signal = defaultdict(list)
    for p, e in used.items():
        if not e["signal"].startswith("GPIO"):
            per_signal[e["signal"]].append(p)
    for s, ps in per_signal.items():
        if len(ps) > 1:
            errors.append(f"signal {s} assigned to several pins: {', '.join(ps)}")
    for r in reserved:
        if r in used:
            errors.append(f"{r}: reserved ({SPECIAL.get(r, 'reserved')}) but used for {used[r]['signal']}")
    for m in warns:
        print("WARN ", m)
    for m in errors:
        print("ERROR", m)
    gpios = [p for p in pins.values() if p.is_gpio]
    print(f"{mcu}: {len(used)}/{len(gpios)} GPIOs allocated, {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


def cmd_table(a) -> int:
    mcu, entries, _ = load_plan(a.plan)
    pins = load_mcu(mcu)
    print("| LQFP pin | GPIO | Signal | Net | Notes |")
    print("|---|---|---|---|---|")
    for e in sorted(entries, key=lambda e: int(pins[e["pin"]].position) if e["pin"] in pins else 0):
        pos = pins[e["pin"]].position if e["pin"] in pins else "?"
        print(f"| {pos} | {e['pin']} | {e['signal']} | {e.get('net', '')} | {e.get('note', '')} |")
    return 0


def cmd_free(a) -> int:
    mcu, entries, _ = load_plan(a.plan)
    pins = load_mcu(mcu)
    used = {e["pin"] for e in entries}
    by_port = defaultdict(list)
    for p in sorted((p for p in pins.values() if p.is_gpio and p.name not in used),
                    key=lambda p: (p.name[1], int(p.name[2:]))):
        by_port[p.name[1]].append(p.name[2:])
    for port, nums in sorted(by_port.items()):
        print(f"P{port}: {' '.join(nums)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("query")
    q.add_argument("pattern")
    q.add_argument("--mcu", default=DEFAULT_MCU)
    q.set_defaults(fn=cmd_query)
    for name, fn in (("check", cmd_check), ("table", cmd_table), ("free", cmd_free)):
        s = sub.add_parser(name)
        s.add_argument("plan")
        s.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
