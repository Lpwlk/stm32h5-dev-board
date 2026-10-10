#!/usr/bin/env python3
"""Audit a KiCad 8/9 schematic hierarchy and export a BOM, without opening KiCad.

Checks:
  * every sheet referenced by the hierarchy exists, and sheet files nobody references
  * unannotated references (R?, #PWR?) and duplicate references across sheets
  * parts with no footprint, no value, or a footprint whose library/file cannot be found
  * the same ref+value used on two sheets (typically a stale copy of a sheet)

Usage:
  kicad_audit.py [project_dir_or_root.kicad_sch] [--bom bom.csv] [--strict]

Exit code 1 if errors were found (warnings do not fail unless --strict).
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sexpr  # noqa: E402

KICAD_FP_DIRS = [
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints",
    "/usr/share/kicad/footprints",
    "C:/Program Files/KiCad/9.0/share/kicad/footprints",
    "C:/Program Files/KiCad/8.0/share/kicad/footprints",
]


def find_root(arg: str) -> Path:
    p = Path(arg)
    if p.is_file():
        return p
    pro = sorted(p.glob("*.kicad_pro"))
    if not pro:
        sys.exit(f"no .kicad_pro in {p}")
    root = pro[0].with_suffix(".kicad_sch")
    if not root.exists():
        sys.exit(f"{root} missing")
    return root


def load_sheet(path: Path):
    return sexpr.parse(path.read_text(encoding="utf-8"))


def walk(root: Path):
    """Yield (path, tree) for every sheet reachable from root, plus child links."""
    seen, queue, links = {}, [root], []
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        tree = load_sheet(path)
        seen[path] = tree
        for sh in sexpr.find_all(tree, "sheet"):
            fname = sexpr.prop(sh, "Sheetfile")
            child = path.parent / fname
            links.append((path, fname, child))
            if child.exists():
                queue.append(child)
    return seen, links


def parts(tree):
    """Placed symbols (not the lib_symbols cache) as dicts."""
    out = []
    for s in sexpr.find_all(tree, "symbol"):
        lib_id = sexpr.find(s, "lib_id")
        if not lib_id:
            continue
        out.append({
            "lib_id": lib_id[1],
            "ref": sexpr.prop(s, "Reference"),
            "value": sexpr.prop(s, "Value"),
            "footprint": sexpr.prop(s, "Footprint"),
            "dnp": (sexpr.find(s, "dnp") or [0, "no"])[1] == "yes",
            "in_bom": (sexpr.find(s, "in_bom") or [0, "yes"])[1] == "yes",
        })
    return out


def footprint_exists(fp: str, project_dir: Path) -> bool | None:
    """True/False if we can tell, None if no libraries were available to check."""
    if ":" not in fp:
        return False
    lib, name = fp.split(":", 1)
    dirs = [Path(d) for d in KICAD_FP_DIRS if Path(d).is_dir()]
    local = project_dir / f"{lib}.pretty"
    if local.is_dir():
        return (local / f"{name}.kicad_mod").exists()
    for d in dirs:
        if (d / f"{lib}.pretty").is_dir():
            return (d / f"{lib}.pretty" / f"{name}.kicad_mod").exists()
    return False if dirs else None


def natkey(r: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", r)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--bom", help="write grouped BOM CSV here")
    ap.add_argument("--strict", action="store_true", help="warnings also fail")
    a = ap.parse_args()

    root = find_root(a.project)
    pdir = root.parent
    sheets, links = walk(root)
    errors, warns = [], []

    for parent, fname, child in links:
        if not child.exists():
            errors.append(f"{parent.name}: sheet file '{fname}' does not exist")
    referenced = {c.resolve() for _, _, c in links} | {root.resolve()}
    for f in sorted(pdir.glob("*.kicad_sch")):
        if f.resolve() not in referenced:
            warns.append(f"{f.name}: not part of the hierarchy (orphan sheet)")

    by_ref = defaultdict(list)
    all_parts = []
    for path, tree in sheets.items():
        for p in parts(tree):
            p["sheet"] = path.name
            all_parts.append(p)
            if not p["ref"].startswith("#"):
                by_ref[p["ref"]].append(p)

    missing_fp = defaultdict(list)
    for p in sorted(all_parts, key=lambda p: (p["sheet"], natkey(p["ref"]))):
        ref, sheet = p["ref"], p["sheet"]
        is_power = ref.startswith("#") or p["lib_id"].startswith("power:")
        if "?" in ref:
            errors.append(f"{sheet}: {ref} ({p['value']}) is not annotated")
        if is_power:
            continue
        if not p["value"]:
            warns.append(f"{sheet}: {ref} has no value")
        if not p["footprint"]:
            missing_fp[sheet].append(ref)
        else:
            ok = footprint_exists(p["footprint"], pdir)
            if ok is False:
                warns.append(f"{sheet}: {ref} footprint '{p['footprint']}' not found in project or KiCad libraries")

    for sheet, refs in sorted(missing_fp.items()):
        errors.append(f"{sheet}: {len(refs)} part(s) without footprint: {' '.join(refs)}")

    for ref, plist in sorted(by_ref.items(), key=lambda kv: natkey(kv[0])):
        if len(plist) > 1 and "?" not in ref:
            where = ", ".join(f"{p['sheet']}[{p['value']}]" for p in plist)
            errors.append(f"duplicate reference {ref}: {where}")

    if a.bom:
        groups = defaultdict(list)
        for p in all_parts:
            if p["ref"].startswith("#") or not p["in_bom"] or p["dnp"]:
                continue
            groups[(p["value"], p["footprint"], p["lib_id"])].append(p["ref"])

        with open(a.bom, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Qty", "Refs", "Value", "Footprint", "Symbol"])
            for (val, fp, sym), refs in sorted(groups.items(), key=lambda kv: natkey(sorted(kv[1], key=natkey)[0])):
                w.writerow([len(refs), " ".join(sorted(refs, key=natkey)), val, fp, sym])
        print(f"BOM: {len(groups)} line items -> {a.bom}")

    n_parts = len([p for p in all_parts if not p["ref"].startswith("#")])
    print(f"{len(sheets)} sheets, {n_parts} parts")
    for m in warns:
        print("WARN ", m)
    for m in errors:
        print("ERROR", m)
    print(f"{len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors or (a.strict and warns) else 0


if __name__ == "__main__":
    sys.exit(main())
