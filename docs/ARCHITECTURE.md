# Architecture: STM32H5 vibration / acceleration dev board

Target: a dev board that measures acceleration and vibration, streams it to a
host PC as fast as practical for live display and interaction, or logs it to an
SD card.

Status of these decisions: **proposed, not yet applied to the schematics.**
Confirm them, then update `HW-SPECS.md` and the sheets.

## 1. Link to the PC: 100BASE-TX Ethernet, not 10BASE-T1S

Run the numbers with `python3 tools/link_budget.py`.

| Case | Sensor payload | USB FS | 10BASE-T1S | 100BASE-TX | microSD |
|---|---|---|---|---|---|
| 1x IIS3DWB, 26.7 kSps, 3 axes, 16 bit | 1.28 Mbit/s | 13 % | 14 % | 1.4 % | 1.6 % |
| 2x IIS3DWB + 2-ch ADC at 1 MSPS | 33 Mbit/s | no | no | 35 % | 42 % |

Findings:

* **One accelerometer is a small data stream (1.3 Mbit/s).** Any link carries it.
  Link speed is not what limits vibration quality; the sensor is (section 2).
* **100BASE-TX is the right main link** because the PC connects with a plain
  cable or NIC, it is full duplex (stream out, commands in, at the same time), it
  has a large headroom for adding an ADC channel later, and the H5 Ethernet MAC
  has IEEE 1588 hardware timestamping (the `ETH_PPS_OUT` pin), which gives you
  time-aligned data across several boards.
* **10BASE-T1S does not fit this board:**
  * a PC has no T1S port; you need a media converter or a bridge board;
  * 10 Mbit/s half-duplex with a shared medium, so the budget shrinks with every
    node that you add (the `--nodes` flag of the tool shows this);
  * the H5 has no T1S MAC; it takes an external MAC-PHY (e.g. LAN8651) over SPI,
    which uses more pins and CPU time than RMII.
  T1S makes sense for a different product: many cheap sensor nodes on one
  twisted pair (about 8 nodes over roughly 25 m, plus power over the same pair
  with PoDL). If you want that later, the sensor board is a better place for it
  than this dev board.
* **USB-C full speed stays,** for power, DFU/bootloader, a CDC console and a
  fallback data path. The H5 has USB **full speed only (12 Mbit/s)**; USB high speed
  (480 Mbit/s) needs a different MCU family (some H7 parts). If you ever need
  more than ~80 Mbit/s of payload, that is the point where changing MCU is
  justified, not before.
* **SD logging** uses SDMMC1 in 4-bit mode. Sustained throughput is easily
  enough (about 160 kB/s per IIS3DWB), but SD cards stall for 100-250 ms during
  internal housekeeping, so the firmware needs a RAM ring buffer of at least
  that duration (the tool prints the size). Use a card with a decent A1/V30 rating and
  write in large aligned blocks.

Recommended Ethernet parts: a 10/100 RMII PHY such as LAN8742A (what the ST Nucleo
H563ZI uses; widest driver support), its own 25 MHz crystal with the PHY
generating the 50 MHz `REF_CLK` for the MCU, and a RJ45 with integrated magnetics.

## 2. Sensors

| Role | Part | Why |
|---|---|---|
| Primary vibration | **ST IIS3DWB** (SPI, LGA-14) | 3 axes, flat response DC-6 kHz, 26.7 kHz output rate, about 75 ug/rtHz noise, +-2/4/8/16 g, 3 KB FIFO, built for vibration monitoring |
| Orientation / motion | a 6-axis IMU (e.g. ICM-42688-P or LSM6DSV) | gyro + low-g accelerometer; optional, the footprint can be DNP |
| Analog expansion | ADC inputs `AIN0/AIN1` on a header | to attach an analog or high-g accelerometer (e.g. ADXL1002) or an IEPE conditioner |

The schematic currently uses an **MPU-6000** (`sensors.kicad_sch`). That part is old, not recommended for
new designs and its accelerometer path is limited to about 1 kHz sampling
(check the datasheet), so it is a poor vibration sensor. Replace it.

Placement and layout notes:

* put the IIS3DWB **close to a mounting hole** and keep the board stiff; the board
  resonance must be above the band you care about;
* away from the board edge, SD socket and RJ45 (insertion forces and heat);
* its own filtered 3V3 (ferrite + 10 uF + 100 nF) and an unbroken ground
  reference under the SPI traces;
* keep the SPI4 lines short, with a series resistor (22-47 R) at the MCU, and give
  `INT1` its own trace so DRDY timing is clean.

## 3. MCU: STM32H563VIT6 (LQFP100) instead of "STM32h553VITx"

* The schematic uses a symbol named `STM32h553VITx`. The CubeMX database
  installed on this Mac contains no H553 entries, and the `...VIT...` (2 MB)
  suffix exists for H562/H563/H573. Pick a real orderable part before
  drawing the rest.
* **H563VIT6**: Cortex-M33 @ 250 MHz, 2 MB flash, 640 KB RAM, 10/100 Ethernet MAC,
  USB FS, SDMMC1/2, LQFP100. The non-`Q` variant uses the LDO (quieter than the SMPS,
  which matters next to an accelerometer).
* `HW-SPECS.md` currently says "Cortex-M7, up to 480 MHz": those are STM32**H7**
  figures. The H5 is a Cortex-M33 at 250 MHz.
* On LQFP100 the **RMII pins are fixed** (`pinplan.toml` has them): REF_CLK=PA1,
  MDIO=PA2, MDC=PC1, CRS_DV=PA7, RXD0/1=PC4/PC5, TX_EN=PA5, TXD0=PB12,
  TXD1=PB15. That forces the sensor SPI onto **SPI4 (PE11-PE14)** because SPI1 uses
  PA5/PA7.
* SDMMC1 uses PC8-PC12 and PD2 (PC10 = D2, so ETH_TXD0 must be on PB12).

`pinplan.toml` is a complete draft allocation (54 of 80 GPIOs used, 26 spare for
headers). Check it with `python3 tools/pinplan.py check pinplan.toml`; it validates
every assignment against ST's pin database, so a bad plan is caught before it is in the
schematic.

DIP-switch question from `ASK.md`: with 26 free GPIOs there is no need for an
IO expander. Wire the 4 DIP switches straight to PD4-PD7 (done in the plan).

## 4. Findings in the current repo

From `python3 tools/kicad_audit.py .`:

* `STM32H7-pill-hw.kicad_pcb` is empty (78 bytes); no layout exists yet.
* 52 placed parts (some duplicated across sheets), **49 without a footprint**; only
  the MCU, the MPU-6000 and the ESD array have one.
* The `User IOs` sheet (`untitled.kicad_sch`) duplicates the LEDs and switches
  that are also in `MCU.kicad_sch`: D1/D2/D3/D5, SW2/SW3/SW4 have duplicate
  references. Keep one copy and delete the other.
* `power.kicad_sch` has only the power LED and the mounting holes. There is no
  regulator, USB power path, protection or sensor supply yet.
* `IO_pins.kicad_sch` is empty and not in the hierarchy.
* `MCU.kicad_sch` has no Ethernet, SD card, USB data connection or sensor SPI wiring yet.
* `git log` is empty and `.gitignore` is empty. Suggested ignores: `*-backups/`,
  `fp-info-cache`, `.DS_Store`, `*.kicad_prl`, `.venv/`.

## 5. Suggested order of work

1. Confirm part choices (H563VIT6, IIS3DWB, LAN8742A, USB-C, microSD, RJ45 part).
2. Fix the MCU symbol, remove the duplicate sheet, add sheets: `ethernet`,
   `sdcard`, a real `power` (5 V in, 3V3 LDO sized ~1 A, clean sensor rail).
3. Draw every part's footprint per `LIBRARY_GUIDELINES.md` and assign them;
   `kicad_audit.py` must report zero errors.
4. Run ERC, then lay out: stackup 4-layer (signal/GND/power/signal), RMII
   length-matched within a few mm, 100 ohm differential for USB and the
   Ethernet TX/RX pairs, solid ground under the sensor.
5. Firmware bring-up using `vib_host.py` as the host: the packet format is
   defined there.
