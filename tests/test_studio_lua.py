from __future__ import annotations

from mmwavelab_dca1000.studio_lua import StudioLuaConfig, generate_iwr1843_studio_lua, write_iwr1843_studio_lua


def test_generate_studio_lua_contains_iwr1843_capture_flow():
    text = generate_iwr1843_studio_lua(StudioLuaConfig(com_port=12, capture_path=r"D:\data\adc_data.bin"))
    assert "COM_PORT = 12" in text
    assert "SOPControl" in text
    assert "DownloadBSSFw" in text
    assert "xwr18xx_radarss.bin" in text
    assert "CaptureCardConfig_StartRecord" in text
    assert "D:\\\\data\\\\adc_data.bin" in text
    assert "FREQ_SLOPE = 77.8" in text


def test_write_studio_lua_reports_resolution(tmp_path):
    cfg = write_iwr1843_studio_lua(tmp_path / "capture.lua", StudioLuaConfig())
    assert (tmp_path / "capture.lua").exists()
    assert 0.037 < cfg.metrics()["range_resolution_m"] < 0.038
