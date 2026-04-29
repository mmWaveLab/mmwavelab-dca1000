# Compatibility Report - 2026-04-29

Host:

- Windows workstation in the mmWaveLab XY-FMCW bench.
- Wired NIC configured as `192.168.33.30`.
- DCA1000 default endpoint: `192.168.33.180`.
- TI CLI backend: `DCA1000EVM_CLI_Control.exe`.

Observed DCA1000 results:

- `query_sys_status`: pass, `System is connected.`
- `reset_fpga`: pass
- `fpga_version`: `FPGA Version : 2.9 [Record]`
- `fpga`: pass
- `record`: pass
- `start_record`: pass

Important compatibility notes:

- TI's DCA1000 CLI rejects JSON files with a UTF-8 BOM.
- TI's DCA1000 CLI can misparse very long JSON paths, so this library stages a short runtime JSON beside the executable.
- `fpga_version` may return a non-zero process code while still producing a valid FPGA version string.
- With no radar LVDS stream, DCA1000 can create only the raw log file and no ADC `.bin`; this is expected and does not indicate a DCA1000 control-path failure.

Current radar-side status:

- IWR1843/DevPack enumerated as `COM9`, `COM10`, `COM11`, and `COM12`.
- None responded to `version` at `115200` or `921600` during this run.
- This suggests the board is not currently running the mmWave demo CLI, or is in a firmware/mmWave Studio mode.

Next hardware step:

- Put IWR1843 into a known mmWave demo CLI state, or run the mmWave Studio Lua firmware-load flow.
- Once a responsive CLI port exists, combine this DCA suite with radar `sensorStart` to verify non-empty ADC `.bin` capture.
