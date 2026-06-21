---
doc_id: CIV51001
title: "Cyclone IV Device Handbook: Device Datasheet"
vendor: "Intel (Altera)"
part_family: Cyclone IV
doc_type: datasheet
version: v2.1
version_date: 2016-03-01
part_numbers: [EP4CE6, EP4CE10, EP4CE22, EP4CGX15, EP4CGX30]
url: https://example.org/docs/civ-51001-v2.1.pdf
---

<!-- page: 1 -->
# 1 Overview
The Cyclone IV device family offers low-power FPGAs in two variants: Cyclone IV E
for the lowest cost, and Cyclone IV GX with integrated 3.125 Gb/s transceivers.
This datasheet covers electrical specifications and switching characteristics.

# 2 Transceiver Specifications (Cyclone IV GX)
## 2.1 Transceiver Data Rate
Cyclone IV GX transceivers support a data rate range from 600 Mb/s to a maximum
of 3.125 Gb/s. The transceivers support protocols including PCI Express Gen1,
Gigabit Ethernet, and Serial RapidIO.

| Symbol | Description | Min | Max | Units |
| --- | --- | --- | --- | --- |
| Data rate | Transceiver data rate | 0.6 | 3.125 | Gb/s |
| REFCLK | Input reference clock | 50 | 156.25 | MHz |

<!-- page: 2 -->
# 3 Recommended Operating Conditions
## 3.1 Supply Voltage
The Cyclone IV core voltage V_CCINT is 1.2 V for the E variant and 1.2 V for the
GX variant. The auxiliary supply V_CCA is 2.5 V and powers the PLL and
transceiver analog circuits.

| Symbol | Description | Min | Typ | Max | Units |
| --- | --- | --- | --- | --- | --- |
| V_CCINT | Core voltage | 1.15 | 1.2 | 1.25 | V |
| V_CCA | PLL/analog supply | 2.375 | 2.5 | 2.625 | V |

## 3.2 Power-On Reset
The Cyclone IV power-on reset (POR) circuit holds the device in reset until all
supplies reach their minimum levels. The fast POR option releases reset within
12 ms; the standard POR releases within 100 ms.
