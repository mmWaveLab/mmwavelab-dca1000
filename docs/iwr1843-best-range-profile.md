# IWR1843 Best Range-Resolution Profile

Generated file:

- `configs/iwr1843_best_range_1tx_256s_3983mhz.cfg`

Core parameters:

- Start frequency: `77.0 GHz`
- Frequency slope: `77.8 MHz/us`
- ADC start: `0.0 us`
- Ramp end: `51.3 us`
- ADC samples: `256`
- Digital output sample rate: `5000 ksps`
- TX/RX: `1 TX + 4 RX`
- Chirps/frame: `16`
- Frame period: `100 ms`

Derived values:

- ADC sample time: `51.2 us`
- Sampled bandwidth: `3.98336 GHz`
- Full ramp bandwidth: `3.99114 GHz`
- Sampled end frequency: `80.98336 GHz`
- Ramp end frequency: `80.99114 GHz`
- Theoretical range resolution: `37.63 mm/bin`
- Theoretical max range: `9.63 m`

Why 1TX first:

- It keeps LVDS throughput low during DCA1000 bring-up.
- It minimizes ambiguous failures while proving raw ADC capture.
- Once the DCA chain produces non-empty `.bin` files, 3TX or SAR-specific profiles can be derived from this baseline.

Risk notes:

- This profile intentionally pushes near the 77-81 GHz sweep limit without crossing 81 GHz.
- If a specific IWR1843 firmware rejects the slope/ramp combination, reduce slope slightly, for example from `77.8` to `76.5 MHz/us`.
- If DCA packet loss appears, increase `packetDelay_us` in the DCA JSON before reducing radar bandwidth.
