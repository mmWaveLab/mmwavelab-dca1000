from __future__ import annotations

from mmwavelab_dca1000.radar_cli import _is_cli_failure, load_cli_config_lines


def test_load_cli_config_lines_skips_comments_and_sensor_start(tmp_path):
    cfg = tmp_path / "profile.cfg"
    cfg.write_text(
        "% comment\n\nflushCfg\n# another comment\nsensorStart\nprofileCfg 0 77\n",
        encoding="utf-8",
    )
    assert load_cli_config_lines(cfg) == ["flushCfg", "profileCfg 0 77"]
    assert load_cli_config_lines(cfg, include_sensor_start=True) == ["flushCfg", "sensorStart", "profileCfg 0 77"]


def test_cli_failure_detects_not_recognized():
    assert _is_cli_failure("'bpmcfg' is not recognized as a cli command")
    assert not _is_cli_failure("ignored: sensor is already stopped\ndone\nmmwdemo:/>")
