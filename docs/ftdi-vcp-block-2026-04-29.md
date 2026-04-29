# FTDI VCP Block, 2026-04-29

This bench state was observed while bringing up DCA1000 + IWR1843.

## Observed

- DCA1000 Ethernet/FPGA control is healthy.
- `USB\VID_0451&PID_FD03\FT8ZO4I3` is present as AR-DevPack/DCA RADAR_FTDI.
- COM9-COM12 map to `\Device\VCP0` through `\Device\VCP3`.
- `mode COM9` through `mode COM12` reports that the devices are not available.
- pyserial and `CreateFileW(access=0)` both return access denied for COM9-COM12.
- FTDI D2XX sees four nodes, but serial/description fields are blank and `FT_Open` returns status `3` for every node.
- XDS110 COM7/COM8 are phantom, so the SDK demo CLI route is not currently online.

## Interpretation

The failure is below the radar protocol layer. A mapped COM port that rejects
even an attribute-only `CreateFileW` open is usually a Windows driver/security
state or a stale kernel lock, not an IWR1843 CLI timeout.

## Fastest Recovery Order

1. Physically replug the DCA1000 `RADAR_FTDI` USB cable.
2. Replug/power-cycle the IWR1843/XDS110 USB cable so COM7/COM8 return from phantom state.
3. Re-run:

   ```powershell
   mmwl-dca1000 serial-diagnostics COM7 COM8 COM9 COM10 COM11 COM12
   ```

4. If COM7 is present and openable, run:

   ```powershell
   mmwl-dca1000 capture-sdk-demo --com-port COM7 --baudrate 115200 --duration-ms 1200 --stop-sensor
   ```

5. If COM9-COM12 remain access-denied after replug, update/reinstall the TI FTDI
   driver from mmWave Studio with an elevated Device Manager or elevated
   `dpinst64.exe`.

TI's DCA1000 debugging handbook also points at USB cable/port and FTDI driver
state when all required COM entries are not usable, and TI support recommends
updating FTDI drivers from the mmWave Studio package before launching Studio.
