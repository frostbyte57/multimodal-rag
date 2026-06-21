---
doc_id: XAPP1234
title: "Using SelectIO and LVDS in 7 Series FPGAs"
vendor: "AMD (Xilinx)"
part_family: Artix-7
doc_type: app_note
version: v1.2
version_date: 2022-03-18
part_numbers: [XC7A35T, XC7A100T]
url: https://example.org/docs/xapp1234-v1.2.pdf
---

<!-- page: 1 -->
# 1 Introduction
This application note describes how to use the SelectIO resources of 7 series
FPGAs to implement LVDS and other differential signaling standards, and how to
apply on-chip termination.

# 2 LVDS Signaling
## 2.1 Supported LVDS Standards
Artix-7 HR I/O banks support LVDS_25 outputs only when V_CCO is 2.5 V. True LVDS
inputs are supported at any HR bank voltage using the DIFF_HSTL or LVDS input
buffer. For LVDS outputs at 3.3 V, use the emulated LVDS (LVDS-compatible)
approach with external resistors.

| Standard | V_CCO | Direction | On-chip term |
| --- | --- | --- | --- |
| LVDS_25 | 2.5 V | Input/Output | DIFF_TERM |
| TMDS_33 | 3.3 V | Input | external |
| MINI_LVDS_25 | 2.5 V | Output | none |

<!-- page: 2 -->
## 2.2 Internal Differential Termination
Enable the internal 100 ohm differential termination on LVDS inputs by setting
the DIFF_TERM attribute to TRUE on the IBUFDS primitive. DIFF_TERM is only
available on inputs, not outputs, and requires V_CCO of 2.5 V on the bank.

# 3 Timing and Constraints
## 3.1 Input Delay Calibration
Use the IDELAYE2 primitive with an IDELAYCTRL reference clock between 190 MHz and
210 MHz to calibrate input delays for source-synchronous LVDS interfaces. Each
IDELAYCTRL calibrates all IDELAYE2 elements within its I/O bank region.
