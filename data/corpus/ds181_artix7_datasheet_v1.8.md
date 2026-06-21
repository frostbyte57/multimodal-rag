---
doc_id: DS181
title: "Artix-7 FPGA Data Sheet: DC and AC Switching Characteristics"
vendor: "AMD (Xilinx)"
part_family: Artix-7
doc_type: datasheet
version: v1.8
version_date: 2024-09-27
part_numbers: [XC7A12T, XC7A35T, XC7A50T, XC7A75T, XC7A100T, XC7A200T]
url: https://example.org/docs/ds181-v1.8.pdf
---

<!-- page: 1 -->
# 1 Overview
The Artix-7 family provides the lowest power and cost per logic cell in the
7 series, optimized for high-throughput, cost-sensitive applications. Devices
range from the XC7A12T through the XC7A200T. This data sheet specifies the DC
and AC switching characteristics for the commercial (C), industrial (I), and
extended (Q) temperature grades.

## 1.1 Speed Grades
Artix-7 devices are available in speed grades -1, -2, and -3, with -3 the
fastest. The -1L grade operates at a reduced V_CCINT of 0.95 V for lower power.

<!-- page: 2 -->
# 2 Transceiver Specifications
Artix-7 devices include GTP transceivers supporting line rates for common
serial protocols including PCI Express, Gigabit Ethernet, and JESD204B.

## 2.1 GTP Transceiver Switching Characteristics
The GTP transceivers in Artix-7 -2 and -3 speed grade devices support a maximum
line rate of 6.6 Gb/s. The minimum supported line rate is 500 Mb/s. For -1 speed
grade devices the maximum line rate is 3.75 Gb/s.

| Symbol | Description | Min | Max | Units |
| --- | --- | --- | --- | --- |
| F_LINE_MAX (-2/-3) | Maximum GTP line rate | — | 6.6 | Gb/s |
| F_LINE_MAX (-1) | Maximum GTP line rate, -1 grade | — | 3.75 | Gb/s |
| F_LINE_MIN | Minimum GTP line rate | 0.5 | — | Gb/s |
| N_GTP (XC7A35T) | Number of GTP transceivers | 4 | 4 | — |

## 2.2 Reference Clock Requirements
The GTP reference clock (MGTREFCLK) must be supplied as a differential pair
with a frequency between 60 MHz and 670 MHz. The reference clock jitter must not
exceed 0.3 ps RMS for reliable operation at the maximum line rate.

<!-- page: 3 -->
# 3 DC Characteristics
## 3.1 Supply Voltages
The recommended internal supply voltage V_CCINT is 1.0 V for standard devices
and 0.95 V for -1L low-voltage devices. The auxiliary supply V_CCAUX is 1.8 V.

| Symbol | Description | Min | Typ | Max | Units |
| --- | --- | --- | --- | --- | --- |
| V_CCINT | Internal supply voltage | 0.95 | 1.0 | 1.05 | V |
| V_CCAUX | Auxiliary supply voltage | 1.71 | 1.8 | 1.89 | V |
| V_CCO | Output driver supply | 1.14 | — | 3.465 | V |

## 3.2 Power-On Ramp
The V_CCINT supply must reach its minimum operating voltage within a monotonic
ramp of 0.2 ms to 50 ms. A ramp slower than 50 ms may cause the device to fail
to initialize and require a power cycle.

<!-- page: 4 -->
# 4 Pin and Bank Specifications
## 4.1 I/O Banks
Artix-7 high-range (HR) I/O banks support V_CCO from 1.2 V to 3.3 V. High-
performance (HP) banks are not present on Artix-7 devices; all banks are HR.
The maximum DC current per I/O pin is 24 mA at LVCMOS33.

## 4.2 Configuration Bank
Bank 0 is the dedicated configuration bank and operates at V_CCO_0 between
1.8 V and 3.3 V. The configuration bank voltage selects the supported
configuration interface voltage levels.
