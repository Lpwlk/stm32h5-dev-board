#!/usr/bin/env python3
"""Lint KiCad footprints (.kicad_mod / .pretty) and their 3D models.

Catches the mistakes that cost a PCB spin or a misleading 3D view:
  * no courtyard, courtyard that does not enclose the pads, no fab outline / silk
  * SMD pads missing paste/mask, THT pads without drill, SMD pad on both sides
  * footprint origin far from the pad centroid (non-connector parts)
  * no 3D model, model file missing, model path not portable
  * 3D model scale/units wrong: STEP bounding box is compared with the pad box
    (catches inch/mm mix-ups and parts floating or sunk relative to the board)

Usage:
  fp_lint.py path/to/Foo.pretty [more.pretty|file.kicad_mod ...] [--project DIR] [--no-3d]

Exit code 1 if any error was found.
"""
from __future__ import annotations

import argparse
import gzip
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sexpr  # noqa: E402

KICAD_SHARE = [
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
    "/usr/share/kicad",
    "C:/Program Files/KiCad/9.0/share/kicad",
    "C:/Program Files/KiCad/8.0/share/kicad",
]
CONNECTOR_HINT = re.compile(r"(conn|header|usb|jack|socket|hole|mount|slot|rj45|sd|battery|switch|button)", re.I)


def fnum(x) -> float:
    return float(x)


def xy_of(node, key):
    n = sexpr.find(node, key)
    return (fnum(n[1]), fnum(n[2])) if n else None


def layers_of(node) -> list[str]:
    n = sexpr.find(node, "layers") or sexpr.find(node, "layer")
    return list(n[1:]) if n else []


def bbox_union(box, pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if box is None:
        return [min(xs), min(ys), max(xs), max(ys)]
    return [min(box[0], *xs), min(box[1], *ys), max(box[2], *xs), max(box[3], *ys)]


def shape_points(s):
    kind = s[0]
    if kind in ("fp_line", "fp_rect"):
        return [xy_of(s, "start"), xy_of(s, "end")]
    if kind == "fp_circle":
        c, e = xy_of(s, "center"), xy_of(s, "end")
        r = math.dist(c, e)
        return [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
    if kind == "fp_arc":
        return [p for p in (xy_of(s, "start"), xy_of(s, "mid"), xy_of(s, "end")) if p]
    if kind == "fp_poly":
        pts = sexpr.find(s, "pts")
        return [(fnum(p[1]), fnum(p[2])) for p in sexpr.find_all(pts, "xy")] if pts else []
    return []


def resolve_model(path: str, project: Path | None, fp_dir: Path) -> Path | None:
    def sub(m):
        var = m.group(1)
        if var == "KIPRJMOD":
            return str(project or fp_dir)
        if re.fullmatch(r"KICAD\d*_3DMODEL_DIR", var):
            for sh in KICAD_SHARE:
                if Path(sh, "3dmodels").is_dir():
                    return str(Path(sh, "3dmodels"))
        return m.group(0)

    p = Path(re.sub(r"\$\{([A-Za-z0-9_]+)\}", sub, path))
    if not p.is_absolute():
        p = fp_dir / p
    return p if p.exists() else None


def step_bbox(path: Path):
    """Bounding box (mm) of all CARTESIAN_POINTs in an ASCII STEP file. Coarse but
    good enough to detect wrong units or a model that is wildly off."""
    op = gzip.open if path.suffix == ".gz" else open
    rx = re.compile(r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)")
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    with op(path, "rt", errors="ignore") as fh:
        for line in fh:
            for m in rx.finditer(line):
                v = [float(g) for g in m.groups()]
                for i in range(3):
                    lo[i], hi[i] = min(lo[i], v[i]), max(hi[i], v[i])
    return (lo, hi) if lo[0] != math.inf else None


def lint(path: Path, project: Path | None, check_3d: bool):
    errs, warns = [], []
    tree = sexpr.parse(path.read_text(encoding="utf-8"))
    if not tree or tree[0] not in ("footprint", "module"):
        return [f"not a footprint file"], []
    name = tree[1]

    crt, fab, silk = None, False, False
    for s in tree:
        if not isinstance(s, list) or not s or not s[0].startswith("fp_"):
            continue
        lay = sexpr.find(s, "layer")
        lname = lay[1] if lay else ""
        if lname.endswith("CrtYd"):
            pts = [p for p in shape_points(s) if p]
            if pts:
                crt = bbox_union(crt, pts)
        elif lname.endswith(".Fab"):
            fab = True
        elif lname.endswith(".SilkS"):
            silk = True

    pads, pad_box = [], None
    for p in sexpr.find_all(tree, "pad"):
        num, ptype, shape = p[1], p[2], p[3]
        at = sexpr.find(p, "at")
        size = sexpr.find(p, "size")
        x, y = fnum(at[1]), fnum(at[2])
        ang = fnum(at[3]) if len(at) > 3 else 0.0
        w, h = fnum(size[1]), fnum(size[2])
        if round(ang) % 180 == 90:
            w, h = h, w
        pad_box = bbox_union(pad_box, [(x - w / 2, y - h / 2), (x + w / 2, y + h / 2)])
        lays = layers_of(p)
        if ptype == "smd":
            has_cu = any(l.endswith(".Cu") for l in lays)
            # Paste-only/mask-only sub-pads (thermal pad paste splitting) carry no copper: fine.
            if has_cu:
                if "F.Cu" in lays and "B.Cu" in lays:
                    errs.append(f"pad {num}: SMD pad on both copper layers")
                side = "F" if "F.Cu" in lays else "B"
                shared = sum(1 for q in sexpr.find_all(tree, "pad") if q[1] == num) > 1
                if f"{side}.Mask" not in lays:
                    (warns if shared else errs).append(f"pad {num}: copper SMD pad has no solder-mask opening")
                if f"{side}.Paste" not in lays and not shared:
                    warns.append(f"pad {num}: no paste layer (ok only for deliberate no-paste pads)")
                if num == "":
                    warns.append("unnamed pad that carries copper")
            elif num != "" and not any(l.endswith((".Paste", ".Mask")) for l in lays):
                errs.append(f"pad {num}: SMD pad on no copper/paste/mask layer")
        elif ptype in ("thru_hole", "np_thru_hole"):
            if not sexpr.find(p, "drill"):
                errs.append(f"pad {num}: through-hole without drill")
        pads.append((num, ptype, x, y))

    if not pads:
        errs.append("no pads")
    if crt is None:
        errs.append("no courtyard (F.CrtYd/B.CrtYd): DRC cannot check clearances to this part")
    elif pad_box and (pad_box[0] < crt[0] - 0.01 or pad_box[1] < crt[1] - 0.01
                      or pad_box[2] > crt[2] + 0.01 or pad_box[3] > crt[3] + 0.01):
        errs.append("courtyard does not enclose all pads")
    if not fab:
        warns.append("no fab-layer outline (assembly drawings/3D alignment reference)")
    if not silk:
        warns.append("no silkscreen outline/marker (pin-1 identification)")

    smd = [p for p in pads if p[1] == "smd"]
    if smd and not CONNECTOR_HINT.search(name):
        cx = sum(p[2] for p in smd) / len(smd)
        cy = sum(p[3] for p in smd) / len(smd)
        if math.hypot(cx, cy) > 0.5:
            warns.append(f"pad centroid is ({cx:.2f}, {cy:.2f}) mm from origin; "
                         "centre the origin for pick-and-place unless this is a connector")

    if check_3d:
        models = sexpr.find_all(tree, "model")
        if not models:
            warns.append("no 3D model")
        for m in models:
            raw = m[1]
            if not raw.startswith("${") :
                warns.append(f"3D path '{raw}' is not variable-based (not portable across machines)")
            f = resolve_model(raw, project, path.parent)
            if f is None:
                errs.append(f"3D model not found: {raw}")
                continue
            scale = [1.0, 1.0, 1.0]
            sc = sexpr.find(m, "scale")
            if sc and sexpr.find(sc, "xyz"):
                scale = [fnum(v) for v in sexpr.find(sc, "xyz")[1:4]]
            if any(abs(s - 1.0) > 1e-6 for s in scale):
                warns.append(f"3D scale {scale}: fix the model units instead of scaling in the footprint")
            rot = sexpr.find(m, "rotate")
            rz = fnum(sexpr.find(rot, "xyz")[3]) if rot and sexpr.find(rot, "xyz") else 0.0
            step = f if f.suffix.lower() in (".step", ".stp", ".gz") else f.with_suffix(".step")
            if step.exists() and pad_box:
                bb = step_bbox(step)
                if bb:
                    lo, hi = bb
                    mx = (hi[0] - lo[0]) * scale[0]
                    my = (hi[1] - lo[1]) * scale[1]
                    if round(rz) % 180 == 90:
                        mx, my = my, mx
                    px, py = pad_box[2] - pad_box[0], pad_box[3] - pad_box[1]
                    ratio = max(mx / px if px else 1, my / py if py else 1)
                    if ratio > 4 or ratio < 0.5:
                        errs.append(f"3D model {mx:.1f}x{my:.1f} mm vs pads {px:.1f}x{py:.1f} mm "
                                    f"(ratio {ratio:.2f}): wrong units/scale or wrong model?")
                    elif ratio > 2.5:
                        warns.append(f"3D model {mx:.1f}x{my:.1f} mm is much larger than pads {px:.1f}x{py:.1f} mm")
                    zmin = lo[2] * scale[2] + (fnum(sexpr.find(sexpr.find(m, "offset"), "xyz")[3])
                                              if sexpr.find(m, "offset") else 0.0)
                    if abs(zmin) > 0.3 and not CONNECTOR_HINT.search(name):
                        warns.append(f"3D model bottom is {zmin:.2f} mm from the board surface (floating or sunk)")
    return errs, warns


def collect(paths):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            yield from sorted(p.rglob("*.kicad_mod"))
        elif p.suffix == ".kicad_mod":
            yield p
        else:
            sys.exit(f"{p}: not a .pretty directory or .kicad_mod")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--project", type=Path, help="project dir, resolves ${KIPRJMOD}")
    ap.add_argument("--no-3d", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true", help="only print files with findings")
    a = ap.parse_args()

    total_e = total_w = n = 0
    for f in collect(a.paths):
        n += 1
        try:
            errs, warns = lint(f, a.project, not a.no_3d)
        except Exception as ex:  # malformed file
            errs, warns = [f"cannot parse: {ex}"], []
        total_e += len(errs)
        total_w += len(warns)
        if errs or warns or not a.quiet:
            print(f"{f.name}: {'FAIL' if errs else 'ok'}")
        for m in errs:
            print(f"   ERROR {m}")
        for m in warns:
            print(f"   WARN  {m}")
    print(f"{n} footprint(s), {total_e} error(s), {total_w} warning(s)")
    return 1 if total_e else 0


if __name__ == "__main__":
    sys.exit(main())
