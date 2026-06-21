---
doc_id: UG470
title: "7 Series FPGAs Configuration User Guide"
vendor: "AMD (Xilinx)"
part_family: Artix-7
doc_type: user_guide
version: v1.15
version_date: 2023-11-02
part_numbers: [XC7A35T, XC7A100T, XC7A200T]
url: https://example.org/docs/ug470-v1.15.pdf
---

<!-- page: 1 -->
# 1 Configuration Overview
7 series FPGAs are configured by loading a bitstream into internal configuration
memory. Configuration can be performed through several interfaces selected by the
mode pins M[2:0].

## 1.1 Configuration Modes
The supported configuration modes are Master SPI, Master BPI, Master SelectMAP,
Slave SelectMAP, JTAG, and Master Serial. The mode is selected at power-up by the
M[2:0] pins and cannot be changed without a reconfiguration.

| M[2:0] | Configuration Mode | Bus Width |
| --- | --- | --- |
| 000 | Master Serial | 1-bit |
| 001 | Master SPI | x1, x2, x4 |
| 010 | Master BPI | x8, x16 |
| 100 | Master SelectMAP | x8, x16 |
| 101 | JTAG | 1-bit |
| 110 | Slave SelectMAP | x8, x16, x32 |

<!-- page: 2 -->
# 2 Master SPI Configuration
In Master SPI mode the FPGA generates the configuration clock (CCLK) and reads
the bitstream from an external SPI flash device. The default CCLK frequency after
power-up is 3 MHz; it can be increased up to 66 MHz using the BitstreamConfig
ConfigRate setting once the bitstream header is read.

## 2.1 SPI Flash Compatibility
The FPGA supports x1, x2 (Dual), and x4 (Quad) SPI read modes. To use Quad mode
the flash device must support the Quad Output Fast Read (6Bh) command, and the
bitstream must be generated with the spi_buswidth set to 4.

## 2.2 CCLK Frequency Guidance
Set ConfigRate conservatively for the target flash. A ConfigRate higher than the
flash maximum read frequency causes configuration CRC errors and the DONE pin
will not assert. If DONE fails to assert, reduce ConfigRate to 3 MHz and retry.

<!-- page: 3 -->
# 3 SelectMAP Configuration
SelectMAP is a parallel configuration interface available in x8, x16, and x32
widths. In slave mode an external controller drives CCLK and the data bus.

## 3.1 SelectMAP Handshaking
The RDWR_B signal selects read or write, and CSI_B is the active-low chip select.
The INIT_B pin signals configuration errors: a low pulse on INIT_B during
configuration indicates a CRC error in the bitstream.

<!-- page: 4 -->
# 4 JTAG Configuration
JTAG configuration is always available regardless of the M[2:0] mode pin setting
and takes priority over other modes. The TCK frequency may be up to 30 MHz for
configuration.

## 4.1 Boundary-Scan and Programming
Standard IEEE 1149.1 boundary-scan instructions are supported. The CFG_IN
instruction loads configuration data, and JSTART starts the device startup
sequence after configuration completes.
