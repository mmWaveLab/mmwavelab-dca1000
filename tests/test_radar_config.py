from __future__ import annotations

from mmwavelab_dca1000.radar_config import generate_iwr1843_best_range_config, parse_profile_metrics


def test_best_range_profile_metrics():
    metrics = parse_profile_metrics(generate_iwr1843_best_range_config())
    assert metrics.num_tx == 1
    assert metrics.num_rx == 4
    assert metrics.chirps_per_frame == 16
    assert 3.98e9 < metrics.sampled_bandwidth_hz < 3.99e9
    assert 0.037 < metrics.range_resolution_m < 0.038
    assert metrics.ramp_end_freq_ghz < 81.0
