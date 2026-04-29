# Serial Ports And Recording Window Notes

## Four FTDI Serial Ports

Connecting the DCA1000/AR-DevPack side of an IWR1843 setup can expose four
serial ports, for example:

- `COM9`
- `COM10`
- `COM11`
- `COM12`

This is normal for the FTDI/DevPack interface. These ports are not automatically
equivalent to a running mmWave demo CLI. A port is considered usable by this
library only if it responds to:

```text
version
```

with mmWave demo text such as `mmWave SDK`, `Platform`, or `xWR`.

If none of the four ports respond, the likely cause is radar-side mode or
firmware state, not a DCA1000 Ethernet failure.

## DCA1000 Recording Black Window

TI's official `DCA1000EVM_CLI_Control.exe start_record` may launch or leave a
visible `DCA1000EVM_CLI_Record.exe` console window. This is especially common
when the capture card is alive but no LVDS stream is arriving from the radar.

The library now handles this by default:

- TI CLI calls are launched with hidden Windows console settings.
- Compatibility suites call `stop_record`.
- Compatibility suites then terminate lingering `DCA1000EVM_CLI_Record.exe`
  helpers only.

This cleanup is intentionally narrow; it does not kill unrelated Python,
PowerShell, mmWave Studio, or radar processes.
