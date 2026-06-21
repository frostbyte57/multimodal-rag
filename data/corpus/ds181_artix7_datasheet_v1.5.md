---
doc_id: DS181
title: "Artix-7 FPGA Data Sheet: DC and AC Switching Characteristics"
vendor: "AMD (Xilinx)"
part_family: Artix-7
doc_type: datasheet
version: v1.5
version_date: 2019-05-14
part_numbers: [XC7A12T, XC7A35T, XC7A50T, XC7A75T, XC7A100T, XC7A200T]
url: https://example.org/docs/ds181-v1.5.pdf
---

<!-- page: 1 -->
# 1 Overview
The Artix-7 family provides the lowest power and cost per logic cell in the
7 series. This data sheet specifies the DC and AC switching characteristics.
NOTE: This is an earlier revision retained for devices qualified against the
v1.5 specification. Newer revisions supersede the values below.

## 1.1 Speed Grades
Artix-7 devices are available in speed grades -1, -2, and -3.

<!-- page: 2 -->
# 2 Transceiver Specifications
Artix-7 devices include GTP transceivers.

## 2.1 GTP Transceiver Switching Characteristics
The GTP transceivers in Artix-7 -2 and -3 speed grade devices support a maximum
line rate of 3.75 Gb/s. The minimum supported line rate is 500 Mb/s.

| Symbol | Description | Min | Max | Units |
| --- | --- | --- | --- | --- |
| F_LINE_MAX | Maximum GTP line rate | — | 3.75 | Gb/s |
| F_LINE_MIN | Minimum GTP line rate | 0.5 | — | Gb/s |

## 2.2 Reference Clock Requirements
The GTP reference clock (MGTREFCLK) must be supplied as a differential pair
with a frequency between 60 MHz and 670 MHz.

<!-- page: 3 -->
# 3 DC Characteristics
## 3.1 Supply Voltages
The recommended internal supply voltage V_CCINT is 1.0 V. The auxiliary supply
V_CCAUX is 1.8 V.
