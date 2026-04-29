# mmWave Studio IWR1843 + DCA1000 Flow

This flow is for the AR-DevPack/FTDI route where Windows exposes multiple
FTDI COM ports and the radar does not answer the mmWave SDK demo CLI command
`version`.

## Current Bench Assumptions

- Radar: IWR1843.
- Capture card: DCA1000.
- Host IP: `192.168.33.30`.
- DCA1000 IP: `192.168.33.180`.
- DCA1000 control/data ports: `4096` / `4098`.
- User-reported physical SOP state on 2026-04-29: `1 0 0`.
- Studio logical SOP command default: `ar1.SOPControl(2)`.
- Candidate FTDI ports observed: `COM9`, `COM10`, `COM11`, `COM12`.

## Generate The Lua Script

```powershell
mmwl-dca1000 generate-studio-lua --com-port 12 --output scripts/iwr1843_dca1000_best_range.lua
```

If mmWave Studio cannot connect, regenerate with another FTDI port:

```powershell
mmwl-dca1000 generate-studio-lua --com-port 9  --output scripts/iwr1843_dca1000_COM9.lua
mmwl-dca1000 generate-studio-lua --com-port 10 --output scripts/iwr1843_dca1000_COM10.lua
mmwl-dca1000 generate-studio-lua --com-port 11 --output scripts/iwr1843_dca1000_COM11.lua
mmwl-dca1000 generate-studio-lua --com-port 12 --output scripts/iwr1843_dca1000_COM12.lua
```

## What The Script Does

1. Resets the radar through Studio/FTDI.
2. Applies `ar1.SOPControl(2)` by default.
3. Connects to the selected COM port at `921600`.
4. Selects `XWR1843` and the `77G` band.
5. Downloads `xwr18xx_radarss.bin` and `xwr18xx_masterss.bin`.
6. Powers on RF, enables RF, and initializes RF.
7. Configures LVDS output and two-lane DCA1000 capture mode.
8. Uses a high-bandwidth 1 TX profile:
   - `77 GHz` start.
   - `77.8 MHz/us` slope.
   - `256` ADC samples.
   - `5000 ksps` sample rate.
   - `3.98336 GHz` sampled bandwidth.
   - `37.63 mm/bin` theoretical range resolution.
9. Starts DCA1000 record and then starts the radar frame.

## Interpretation

The DCA1000-only suite already proves Ethernet control and FPGA record mode.
The Studio Lua flow is the next radar-side proof: a successful run should
produce a non-empty raw ADC output at the script's `SAVE_DATA_PATH`.

If all DCA1000 commands pass but this Lua script fails before `StartFrame`, the
remaining fault is likely radar-side connection, SOP/reset, firmware download,
or the selected FTDI COM channel.

## Send The Script To An Open Studio Session

mmWave Studio exposes a local RSTD network bridge after this command is run in
the Studio Lua shell:

```lua
RSTD.NetStart()
```

After that one-time bridge is open, the Python CLI can inject the generated
script:

```powershell
mmwl-dca1000 run-studio-lua scripts/iwr1843_dca1000_best_range.lua
```

If this command reports that it cannot connect to `127.0.0.1:2777`, Studio is
not running or `RSTD.NetStart()` has not been executed in that Studio session.
