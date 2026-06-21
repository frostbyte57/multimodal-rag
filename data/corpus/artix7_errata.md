---
doc_id: EN191
title: "Artix-7 FPGA Silicon Errata"
vendor: "AMD (Xilinx)"
part_family: Artix-7
doc_type: errata
version: v1.9
version_date: 2024-06-10
part_numbers: [XC7A35T, XC7A50T, XC7A100T, XC7A200T]
url: https://example.org/docs/en191-artix7-errata-v1.9.pdf
---

<!-- page: 1 -->
# 1 Introduction
This document describes known silicon issues for Artix-7 devices, the affected
silicon steppings, and available workarounds. Steppings are identified by the
device DNA and the package marking revision code.

<!-- page: 2 -->
# 2 GTP Transceiver Errata
## 2.1 EN-101: GTP PLL fails to lock at startup on cold boot
<!-- meta: errata_id=EN-101 product=XC7A35T,XC7A50T stepping=ES1 has_workaround=yes -->
On ES1 silicon, the GTP channel PLL may intermittently fail to achieve lock when
the device powers up below 0 C. The failure manifests as the TXRESETDONE signal
never asserting after a reset sequence.

**Affected steppings:** ES1 only. Production (Rev B) silicon is not affected.

**Workaround:** Implement a reset-retry state machine that toggles GTPLLRESET and
re-asserts GTTXRESET if TXRESETDONE does not assert within 50 us. Repeat up to
four times. AMD recommends migrating designs to production stepping where
possible.

## 2.2 EN-104: GTP RX elastic buffer overflow at 6.6 Gb/s
<!-- meta: errata_id=EN-104 product=XC7A50T,XC7A100T stepping=ES1,ES2 has_workaround=yes -->
At the maximum line rate of 6.6 Gb/s, the RX elastic buffer can overflow when the
clock correction sequence is shorter than 4 bytes, producing intermittent
8b/10b disparity errors.

**Affected steppings:** ES1 and ES2.

**Workaround:** Use a clock correction sequence of at least 4 bytes, or enable RX
buffer bypass and use the manual phase alignment procedure. Fixed in production
stepping (Rev B).

<!-- page: 3 -->
# 3 Configuration Errata
## 3.1 EN-118: SPI x4 configuration fails with certain flash devices
<!-- meta: errata_id=EN-118 product=XC7A35T,XC7A100T,XC7A200T stepping=ES1,ES2,Production has_workaround=yes -->
When using Master SPI x4 (Quad) configuration with flash devices that drive the
DQ pins during the dummy cycle, configuration may fail to start and the DONE pin
does not assert. This affects all steppings including production.

**Affected steppings:** ES1, ES2, and Production.

**Workaround:** Reduce the configuration to SPI x1 or x2 mode, or select a flash
device that tristates DQ during dummy cycles. Setting ConfigRate to 3 MHz does
not resolve this issue.

<!-- page: 4 -->
# 4 Power Errata
## 4.1 EN-125: Elevated V_CCAUX quiescent current on ES1
<!-- meta: errata_id=EN-125 product=XC7A200T stepping=ES1 has_workaround=no -->
ES1 silicon of the XC7A200T exhibits V_CCAUX quiescent current up to 30% above
the data sheet typical value. There is no functional impact.

**Affected steppings:** ES1 only.

**Workaround:** None required; budget power supply margin accordingly. Resolved
in production stepping.
