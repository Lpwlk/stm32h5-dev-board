# tools

Python 3.11+ (tested on 3.12). All but the plot feature are stdlib only. The
system `python3` here is a 3.15 alpha whose numpy is broken, so use 3.12:

```
python3.12 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt   # only for --plot
```

| Tool | What it does |
|---|---|
| `pinplan.py` | Validates `pinplan.toml` against ST's CubeMX pin database; `query ETH_` shows which pins can carry a signal; `table` writes the pinout markdown; `free` lists unused GPIOs |
| `kicad_audit.py` | Reads the schematic hierarchy without KiCad: missing/unknown footprints, duplicate or unannotated references, orphan sheets, BOM CSV (`--bom`) |
| `fp_lint.py` | Lints `.kicad_mod` / `.pretty`: courtyard, pad layers, drills, origin, missing 3D model, wrong 3D scale (STEP bounding box vs pads) |
| `link_budget.py` | Sensor data rate vs USB FS, 10BASE-T1S, 100BASE-TX and SD, with latency and buffer size |
| `vib_host.py` | Packet format + `sim` (fake board), `rx` (UDP receiver, loss counter, log, plot) and `read` (decode SD logs to CSV/plot) |
| `sexpr.py` | Small KiCad S-expression parser used by the two KiCad tools |

Quick demo without hardware:

```
python3.12 tools/vib_host.py sim &                     # fake board on UDP 5005
.venv/bin/python tools/vib_host.py rx --plot           # time + spectrum of 0.5 s
```
