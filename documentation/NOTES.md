<samp> 

<div align="center">

# 🔧 STM32h5 dev board notebook

This file is being used as a notebook for the `STM32h5 dev board` project. Any piece of information that has been useful to design the board should be included here in the associated section. Manufacturer or chip specific information won't be details and the associated datasheet link will be included

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

<table>
  <thead>
    <tr>
      <th colspan="6" align="center">USB-C connector — Pinout (A ↔ B)</th>
    </tr>
    <tr>
      <th colspan="3" align="center">A</th>
      <th colspan="3" align="center">B</th>
    </tr>
    <tr>
      <th align="center">Pin (A)</th>
      <th align="center">Name (A)</th>
      <th>Description (A)</th>
      <th>Description (B)</th>
      <th align="center">Name (B)</th>
      <th align="center">Pin (B)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td align="center">A1</td>
      <td align="center">GND</td>
      <td>Ground return</td>
      <td>Ground return</td>
      <td align="center">GND</td>
      <td align="center">B1</td>
    </tr>
    <tr>
      <td align="center">A2</td>
      <td align="center">SSTXp1 ("TX1+")</td>
      <td>SuperSpeed differential pair #1, transmit, positive</td>
      <td>SuperSpeed differential pair #3, transmit, positive</td>
      <td align="center">SSTXp2 ("TX2+")</td>
      <td align="center">B2</td>
    </tr>
    <tr>
      <td align="center">A3</td>
      <td align="center">SSTXn1 ("TX1−")</td>
      <td>SuperSpeed differential pair #1, transmit, negative</td>
      <td>SuperSpeed differential pair #3, transmit, negative</td>
      <td align="center">SSTXn2 ("TX2−")</td>
      <td align="center">B3</td>
    </tr>
    <tr>
      <td align="center">A4</td>
      <td align="center">VBUS</td>
      <td>Bus power</td>
      <td>Bus power</td>
      <td align="center">VBUS</td>
      <td align="center">B4</td>
    </tr>
    <tr>
      <td align="center">A5</td>
      <td align="center">CC1</td>
      <td>Configuration channel</td>
      <td>Configuration channel</td>
      <td align="center">CC2</td>
      <td align="center">B5</td>
    </tr>
    <tr>
      <td align="center">A6</td>
      <td align="center">D+</td>
      <td>USB 2.0 differential pair, position 1, positive</td>
      <td>USB 2.0 differential pair, position 2, positive[a]</td>
      <td align="center">D+</td>
      <td align="center">B6</td>
    </tr>
    <tr>
      <td align="center">A7</td>
      <td align="center">D−</td>
      <td>USB 2.0 differential pair, position 1, negative</td>
      <td>USB 2.0 differential pair, position 2, negative[a]</td>
      <td align="center">D−</td>
      <td align="center">B7</td>
    </tr>
    <tr>
      <td align="center">A8</td>
      <td align="center">SBU1</td>
      <td>Sideband use (SBU)</td>
      <td>Sideband use (SBU)</td>
      <td align="center">SBU2</td>
      <td align="center">B8</td>
    </tr>
    <tr>
      <td align="center">A9</td>
      <td align="center">VBUS</td>
      <td>Bus power</td>
      <td>Bus power</td>
      <td align="center">VBUS</td>
      <td align="center">B9</td>
    </tr>
    <tr>
      <td align="center">A10</td>
      <td align="center">SSRXn2 ("RX2−")</td>
      <td>SuperSpeed differential pair #4, receive, negative</td>
      <td>SuperSpeed differential pair #2, receive, negative</td>
      <td align="center">SSRXn1 ("RX1−")</td>
      <td align="center">B10</td>
    </tr>
    <tr>
      <td align="center">A11</td>
      <td align="center">SSRXp2 ("RX2+")</td>
      <td>SuperSpeed differential pair #4, receive, positive</td>
      <td>SuperSpeed differential pair #2, receive, positive</td>
      <td align="center">SSRXp1 ("RX1+")</td>
      <td align="center">B11</td>
    </tr>
    <tr>
      <td align="center">A12</td>
      <td align="center">GND</td>
      <td>Ground return</td>
      <td>Ground return</td>
      <td align="center">GND</td>
      <td align="center">B12</td>
    </tr>
  </tbody>
</table>