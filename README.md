# mmwavelab-dca1000

Python automation for TI DCA1000 + xWR raw ADC capture chains.

This repository is designed for the `mmWaveLab` workflow:

- Probe the host NIC and DCA1000 aliveness.
- Generate DCA1000 JSON files without UTF-8 BOM, which the TI CLI rejects.
- Wrap TI's `DCA1000EVM_CLI_Control.exe` with structured JSON reports.
- Run a DCA-only compatibility suite before involving a radar board.
- Probe xWR/IWR CLI serial ports.
- Generate high-bandwidth IWR1843 profiles for best practical range resolution.

The first target setup is:

- Radar: TI IWR1843 / xWR1843 family.
- Capture card: TI DCA1000.
- Host IP: `192.168.33.30`.
- DCA1000 IP: `192.168.33.180`.
- Control UDP: `4096`.
- Data UDP: `4098`.

## Why This Exists

DCA1000 bring-up is fragile in small ways that waste lab time:

- The TI CLI can fail on long JSON paths.
- The TI CLI rejects JSON files written with a UTF-8 BOM.
- `fpga_version` may return a non-zero process code while still printing a valid version.
- DCA1000 can be perfectly alive while the radar CLI is not in mmWave demo mode.

This package keeps those edge cases visible and machine-readable.

## Install

```powershell
cd C:\Users\ijink\Desktop\mmwavelab-dca1000
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

## Quick Start

Generate the best-range IWR1843 profile:

```powershell
mmwl-dca1000 generate-iwr1843-config --output configs/iwr1843_best_range_1tx_256s_3983mhz.cfg
```

Run DCA1000 preflight:

```powershell
mmwl-dca1000 dca-suite --dca-json configs/dca1000_iwr1843.json --output-dir captures/dca_suite
```

Probe possible radar CLI ports:

```powershell
mmwl-dca1000 probe-radar-cli COM9 COM10 COM11 COM12
```

## Best Range Profile

The bundled best-range IWR1843 profile uses:

- Start frequency: `77 GHz`
- Slope: `77.8 MHz/us`
- ADC samples: `256`
- Sample rate: `5000 ksps`
- ADC time: `51.2 us`
- Sampled bandwidth: `3.98336 GHz`
- Theoretical range resolution: `37.63 mm/bin`
- 1 TX + 4 RX, 16 chirps/frame, 100 ms frame period

This is a link-friendly high-bandwidth profile. It is intended to prove the
DCA1000 raw ADC chain first. SAR and NDT profiles can then trade frame rate,
SNR, and motion timing against this baseline.

See `docs/iwr1843-best-range-profile.md` for the derivation.

## Current Bench Compatibility

On 2026-04-29 the DCA1000 control path passed:

- DCA1000 aliveness query.
- FPGA reset/configuration.
- FPGA version query, observed `2.9 [Record]`.
- Record configuration.
- Timed start-record command.

The IWR1843/DevPack serial ports enumerated, but no port responded to mmWave
demo CLI `version` yet. See `docs/compatibility-2026-04-29.md`.

## Hardware Notes

If the DCA suite passes but `probe-radar-cli` shows no responsive port, the
radar is probably not running the mmWave demo CLI firmware or is in an SOP
mode intended for mmWave Studio/firmware loading. That is not a DCA1000
failure; it is a radar-side mode/firmware issue.
