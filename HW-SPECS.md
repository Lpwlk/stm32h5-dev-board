<samp> 

<div align="center">

# 🔧 STM32h5 dev board specification

This document defines the HW specification for the `STM32h5 dev board` project. Core HW informations & every intended use-cases will be covered here.

</div>

## Table of contents

1 - [Overview](#1-overview-↑) <br>
2 - [Hardware specifications](#2-hardware-specifications-↑) <br>
&nbsp; 2.1 - [Microcontroller](#21-microcontroller) <br>
&nbsp; 2.2 - [Power supply](#22-power-supply) <br>
&nbsp; 2.3 - [Connectivity](#23-connectivity) <br>
&nbsp; 2.4 - [User interface](#24-user-interface) <br>
&nbsp; 2.5 - [EMC targets](#25-emc-targets) <br>
&nbsp; 2.6 - [Other features](#26-other-features) <br>
3 - [Pinout](#3-pinout-↑) <br>
4 - [References](#4-references-↑) <br>
&nbsp; 4.1 - [Official](#41-official) <br>
&nbsp; 4.2 - [Community](#42-community) <br>
5 - [Revision history](#5-revision-history-↑) <br>

## 1. Overview [↑](#table-of-contents)

**Project Name:** STM32h5 Dev Board
**Target MCU:** STM32h5xxx (LQFP100)
**Author:** Lpwlk  
**Date:** 2025-09-23
**Version:** 1.0

**Description:**  
This project aims to design and implement a premium development board based on the STM32h5 series microcontroller (LQFP100 package), providing essential peripherals and interfaces for rapid prototyping, evaluation & applicative embedded projects.

## 2. Hardware specifications [↑](#table-of-contents)

### 2.1 Microcontroller 

- **Model:** STM32h5xxx (LQFP100)
- **Core:** ARM Cortex-M7
- **Clock:** Up to 480 MHz
- **Flash/RAM:** [Specify exact part number and memory sizes]

### 2.2 Power Supply

- **Input Voltage:** 5V (USB-C or barrel jack)
- **Onboard Regulators:** 3.3V, 1.8V
- **Protection:** Reverse polarity, ESD

### 2.3 Connectivity

- **USB:** USB FS/HS (USB-C)
- **UART:** 2x (with level shifters)
- **I2C/SPI:** 2x each (broken out to headers)
- **Headers:** All GPIOs on 2.54mm pitch headers
- **Debug:** SWD/JTAG header

### 2.4 User Interface

- **Buttons:** Reset, User
- **LEDs:** Power, Status, User

### 2.5 EMC targets

- **Oscillators:** 8 MHz HSE, 32.768 kHz LSE
- **MicroSD slot:** [Yes/No]
- **Display:** [Optional, e.g., 0.96" OLED]

### 2.6 Other Features

- **Oscillators:** 8 MHz HSE, 32.768 kHz LSE
- **MicroSD slot:** [Yes/No]
- **Display:** [Optional, e.g., 0.96" OLED]

## 3. Pinout [↑](#table-of-contents)

| Pin | STM32h5 Function | Board Label | Notes           |
|-----|------------------|-------------|-----------------|
| 1   | VDD              | 3V3         | Power           |
| 2   | GND              | GND         | Ground          |
| ... | ...              | ...         | ...             |

*Attach a full pinout table or diagram.*

## 4. Mechanical details [↑](#table-of-contents)

- **Schematic:** [Link or attach PDF]
- **PCB Layout:** [Link or attach Gerber files]
- **Board Dimensions:** [e.g., 80mm x 60mm]

## 4. References [↑](#table-of-contents)

### 4.1. Official

- [STM32h5 Reference Manual](https://www.st.com/resource/en/reference_manual/dm00314099.pdf)
- [STM32Cubeh5 Firmware Package](https://www.st.com/en/embedded-software/stm32cubeh5.html)
- [Board Schematic PDF](link-to-schematic)

### 4.2. Community

## 5. Revision history [↑](#table-of-contents)

| Date       | Version | Author         | Changes           |
|------------|---------|----------------|-------------------|
| 2025-09-23 | 1.0     | Loic PAWLICKI  | Initial document  |