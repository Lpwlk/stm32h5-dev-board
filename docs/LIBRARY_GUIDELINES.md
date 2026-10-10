# Footprint and 3D model guidelines

Goal: every part on the board has a footprint you have verified against the
datasheet, and a 3D model that matches it, so the first PCB is not a spin-0 for
bad land patterns and the enclosure fits.

Layout of the repo for this:

```
Footprints/H5Dev.pretty/   project footprints (one .kicad_mod per part)   -> fp-lib-table "H5Dev"
3D/H5Dev.3dshapes/         STEP (+ optional WRL) models, same base name as the footprint
Symbols/MyLib.kicad_sym    project symbols                               -> sym-lib-table "MyLib"
```

Never edit the KiCad stock libraries and never use absolute paths. Copy a stock
footprint into `H5Dev.pretty` if you need to change it, so the change travels
with the repo.

## 1. Choosing a footprint source (in this order)

1. **KiCad official library**, used as is. Fine for passives (`Capacitor_SMD`,
   `Resistor_SMD`, 0402 or 0603), `Package_QFP` LQFP-100, `Package_SO`, `Crystal`,
   `LED_SMD`, `Button_Switch_SMD`. Reference it directly, do not copy it.
2. **KiCad official library + your check.** For anything specific (USB-C,
   microSD, RJ45, LGA sensor) pick a stock footprint named after your exact
   manufacturer part, e.g. `Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal`
   or `Connector_Card:microSD_HC_Hirose_DM3D-SF`. If the stock one is for a
   different part number, it is a different part.
3. **Manufacturer / aggregator download** (SnapMagic, Ultra Librarian, EasyEDA/LCSC via
   `pip install easyeda2kicad`). Treat as a draft. They are frequently wrong
   on pad sizes, paste, courtyard and origin, and 3D models are often misplaced.
4. **Generate it.** KiCad Footprint Wizard for QFP/QFN/SOIC/headers, or the
   `kicad-footprint-generator` scripts when you need many variants.
5. **Draw it by hand** from the datasheet "recommended land pattern". Last
   resort, but the only option for odd mechanical parts.

Whatever the source, the **datasheet land pattern is the reference**, not the
downloaded footprint and not the 3D model.

## 2. Footprint rules (condensed from the KiCad Library Convention, klc.kicad.org)

| Item | Rule |
|---|---|
| Origin | Centre of the body for ICs and passives (pin 1 for through-hole headers). Centroid of the SMD pads within ~0.5 mm unless it is a connector |
| Name | Describes the package, not the board: `LGA-14_2.5x3mm_P0.5mm`. Include the manufacturer if the pattern is part-specific |
| Pin 1 | Marked on silkscreen (outside the pads) and on F.Fab. Check the orientation against the datasheet top view |
| Courtyard | Closed polygon on F.CrtYd, ~0.25 mm beyond pads/body (0.5 mm for connectors), must enclose every pad, line 0.05 mm |
| Silkscreen | F.SilkS, 0.12 mm minimum, **never over pads or exposed copper**. Body outline may be broken where it would touch pads |
| Fab | Body outline on F.Fab (0.1 mm), reference and value as `${REFERENCE}` / `${VALUE}` text on Fab |
| SMD pads | Layers `F.Cu F.Paste F.Mask`. Exposed/thermal pads: split the paste into several smaller openings (50-70 % coverage) |
| THT pads | Drill = max lead diameter + 0.2..0.3 mm. Annular ring >= 0.25 mm. Mechanical/shield tabs: NPTH or named pad, intentionally |
| Mounting holes | NPTH, drill = screw clearance (M3: 3.2 mm), keepout courtyard bigger than the screw head |
| Properties | Description, datasheet URL and MPN filled in. They end up in the BOM |

Parts on this board that need extra attention:

* **IIS3DWB (LGA-14, 2.5 x 3 mm).** LGA pads are under the body, so you cannot
  rework them visually. Take pad size and stencil from the ST datasheet package
  section; the KiCad `LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` is the likely
  starting point, but verify the pad numbering and pin 1 against ST's drawing.
* **RJ45 with integrated magnetics.** Use the footprint of the exact part (shield
  tabs, LED pins, keepout below the magnetics). Do not substitute a "close"
  RJ45.
* **USB-C receptacle.** The `USB_C_Connector_16P` symbol in `MyLib` must match
  the pin names of the footprint you pick (A1/B12 power/ground, A4/B9 VBUS, A5/B5
  CC, A6/A7 D+/D-, shield pads). Check the symbol-to-pad mapping in the
  netlist, not just the symbol. A USB-C footprint with the wrong shield-pin
  numbering silently ties the shield to the wrong net.
* **microSD push-push socket.** Check that the footprint has the card-detect
  switch pins and the shell/shield pads for the exact part. Cheap
  footprints often leave them out.
* **LQFP-100.** Use the stock `LQFP-100_14x14mm_P0.5mm`. The exposed-pad-free
  QFP needs no thermal pad.

## 3. 3D models

* **Format:** STEP is the one that matters (MCAD export, accurate, coloured).
  Add a `.wrl` next to it only if you want nicer viewer rendering. The stock
  KiCad models ship both.
* **Source, in order of preference:**
  1. KiCad stock model that the stock footprint already points to.
  2. Manufacturer STEP for the exact part (Hirose, Molex, Amphenol, Wurth, GCT
     and ST all publish them). Connectors matter most because enclosure fit
     depends on them.
  3. Generate a parametric one: CadQuery (`kicad-packages3D-generator`) or
     FreeCAD with the KicadStepUp workbench. Best for LQFP/QFN/LGA/passives.
  4. SnapMagic / EasyEDA models: check scale and orientation carefully.
* **Conventions the footprint depends on:**
  * Units mm, model origin = footprint origin, board surface at Z = 0, +Z up.
  * Pin 1 of the model on the same corner as pin 1 of the footprint.
  * Keep `scale (1 1 1)` and `offset (0 0 0)` in the footprint. If you need to
    scale or shift, fix the model file instead.
  * File base name = footprint name, stored in `3D/H5Dev.3dshapes/`.
  * Path in the footprint is variable based: `${KIPRJMOD}/3D/H5Dev.3dshapes/NAME.step`.
    Stock models use `${KICAD8_3DMODEL_DIR}/...`.
  * Keep each file under roughly 2 MB. Dense vendor meshes make the 3D viewer
    sluggish; simplify or re-export if needed. Colours: black plastic body,
    metallic leads, so that pin 1 and orientation are obvious.
* **Embedding (KiCad 8+):** footprints can embed their 3D model so a footprint
  copied to another project cannot lose it. Useful for the few custom parts.

## 4. Verification workflow

Do this per new footprint, before it is used on the board:

1. `python3 tools/fp_lint.py Footprints/H5Dev.pretty --project .` — catches no
   courtyard, pad layer mistakes, missing/misplaced 3D files and wrong 3D
   scale (compares STEP bounding box with the pads).
2. Overlay the datasheet drawing: in the footprint editor use the measuring tool
   on pitch, pad span and pad length against the datasheet dimensions.
3. Look at it in the 3D viewer: model sits on the board (not floating, not
   sunk), pin 1 aligned, pins land on the pads.
4. For anything hand-soldered or mechanically critical (connectors, sockets,
   LGA): **print the footprint 1:1** and hold the real part (or its datasheet
   outline) on top. Cheapest bug catch in hardware.
5. After the layout: `python3 tools/kicad_audit.py .` shows every symbol that has
   no footprint assigned, then run DRC, then
   `kicad-cli pcb export step` and check height and connector overhang
   against the enclosure in your MCAD tool.

Stock-library caveat found with the linter: `Sensor_Motion:InvenSense_QFN-24_4x4mm_P0.5mm`
(the MPU-6000 footprint used today) points at a 3D model file
(`QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.6mm`) that does not exist in the installed KiCad
3D library. Several `Package_QFP` exposed-pad variants have the same problem.
A missing model is only cosmetic, but it shows the stock libraries
need the same check as your own.
