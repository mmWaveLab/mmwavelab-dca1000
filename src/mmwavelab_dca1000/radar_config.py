from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


LIGHT_SPEED_M_S = 299_792_458.0


@dataclass
class RadarProfileMetrics:
    start_freq_ghz: float
    slope_mhz_us: float
    adc_start_us: float
    ramp_end_us: float
    adc_samples: int
    sample_rate_ksps: int
    num_tx: int
    num_rx: int
    chirps_per_frame: int
    frame_period_ms: float
    adc_time_us: float
    sampled_bandwidth_hz: float
    full_ramp_bandwidth_hz: float
    sampled_end_freq_ghz: float
    ramp_end_freq_ghz: float
    range_resolution_m: float
    max_range_m: float

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def clean_cfg_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("%", "#", "//")):
            continue
        for marker in ("%", "#", "//"):
            if marker in line:
                line = line.split(marker, 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def parse_profile_metrics(text: str) -> RadarProfileMetrics:
    profile = frame = channel = None
    for line in clean_cfg_lines(text):
        tokens = line.split()
        if tokens[0] == "profileCfg":
            profile = tokens
        elif tokens[0] == "frameCfg":
            frame = tokens
        elif tokens[0] == "channelCfg":
            channel = tokens
    if profile is None or frame is None or channel is None:
        raise ValueError("profileCfg, frameCfg, and channelCfg are required")

    start_freq_ghz = float(profile[2])
    idle_time_us = float(profile[3])
    adc_start_us = float(profile[4])
    ramp_end_us = float(profile[5])
    slope_mhz_us = float(profile[8])
    adc_samples = int(profile[10])
    sample_rate_ksps = int(profile[11])
    rx_mask = int(channel[1])
    tx_mask = int(channel[2])
    num_rx = rx_mask.bit_count()
    num_tx = tx_mask.bit_count()
    chirp_start = int(frame[1])
    chirp_end = int(frame[2])
    loops = int(frame[3])
    frame_period_ms = float(frame[5])

    adc_time_s = adc_samples / (sample_rate_ksps * 1e3)
    adc_time_us = adc_time_s * 1e6
    sampled_bandwidth_hz = slope_mhz_us * 1e12 * adc_time_s
    full_ramp_bandwidth_hz = slope_mhz_us * 1e12 * ramp_end_us * 1e-6
    sampled_end_freq_ghz = start_freq_ghz + slope_mhz_us * (adc_start_us + adc_time_us) / 1000.0
    ramp_end_freq_ghz = start_freq_ghz + slope_mhz_us * ramp_end_us / 1000.0
    range_resolution_m = LIGHT_SPEED_M_S / (2.0 * sampled_bandwidth_hz)
    max_range_m = (sample_rate_ksps * 1e3) * LIGHT_SPEED_M_S / (2.0 * slope_mhz_us * 1e12)
    chirps_per_frame = (chirp_end - chirp_start + 1) * loops
    _ = idle_time_us

    return RadarProfileMetrics(
        start_freq_ghz=start_freq_ghz,
        slope_mhz_us=slope_mhz_us,
        adc_start_us=adc_start_us,
        ramp_end_us=ramp_end_us,
        adc_samples=adc_samples,
        sample_rate_ksps=sample_rate_ksps,
        num_tx=num_tx,
        num_rx=num_rx,
        chirps_per_frame=chirps_per_frame,
        frame_period_ms=frame_period_ms,
        adc_time_us=adc_time_us,
        sampled_bandwidth_hz=sampled_bandwidth_hz,
        full_ramp_bandwidth_hz=full_ramp_bandwidth_hz,
        sampled_end_freq_ghz=sampled_end_freq_ghz,
        ramp_end_freq_ghz=ramp_end_freq_ghz,
        range_resolution_m=range_resolution_m,
        max_range_m=max_range_m,
    )


def generate_iwr1843_best_range_config() -> str:
    """Return a high-bandwidth 1TX profile for IWR1843 + DCA1000.

    The sampled ADC window spans 3.98336 GHz, giving ~37.63 mm theoretical
    range resolution while keeping data rate low for bring-up.
    """

    lines = [
        "% IWR1843 + DCA1000 best practical range-resolution bring-up profile.",
        "% 1TX + 4RX, complex ADC, 256 samples, 16 chirps/frame.",
        "% Sampled bandwidth: 3.98336 GHz; theoretical range resolution: 37.63 mm/bin.",
        "sensorStop",
        "flushCfg",
        "dfeDataOutputMode 1",
        "channelCfg 15 1 0",
        "adcCfg 2 1",
        "adcbufCfg -1 0 1 1 1",
        "lowPower 0 0",
        "profileCfg 0 77 120 0 51.3 0 0 77.8 1 256 5000 0 0 30",
        "chirpCfg 0 0 0 0 0 0 0 1",
        "frameCfg 0 0 16 0 100 1 0",
        "guiMonitor -1 0 0 0 0 0 0",
        "cfarCfg -1 0 2 8 4 3 0 15 1",
        "cfarCfg -1 1 0 4 2 3 1 15 1",
        "multiObjBeamForming -1 1 0.5",
        "clutterRemoval -1 0",
        "calibDcRangeSig -1 0 -5 8 256",
        "extendedMaxVelocity -1 0",
        "bpmCfg -1 0 0 1",
        "lvdsStreamCfg -1 1 1 0",
        "compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0",
        "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
        "CQRxSatMonitor 0 3 4 95 0",
        "CQSigImgMonitor 0 63 4",
        "analogMonitor 0 0",
        "aoaFovCfg -1 -90 90 -90 90",
        "cfarFovCfg -1 0 0.20 4.99",
        "cfarFovCfg -1 1 -2.39 2.39",
        "calibData 0 0 0",
    ]
    return "\n".join(lines) + "\n"


def write_iwr1843_best_range_config(path: str | Path) -> RadarProfileMetrics:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = generate_iwr1843_best_range_config()
    target.write_text(text, encoding="utf-8")
    return parse_profile_metrics(text)
