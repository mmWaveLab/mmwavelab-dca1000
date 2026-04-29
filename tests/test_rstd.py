from __future__ import annotations

from mmwavelab_dca1000.rstd import build_dofile_command, build_rstd_powershell_command


def test_build_dofile_command_escapes_windows_path(tmp_path):
    script = tmp_path / "a b" / "capture.lua"
    command = build_dofile_command(script)
    assert command.startswith("dofile(")
    assert "\\\\" in command
    assert "capture.lua" in command


def test_build_rstd_powershell_command_mentions_netstart():
    ps = build_rstd_powershell_command('WriteToLog("hello\\n", "green")')
    assert "RtttNetClient" in ps
    assert "SendCommand" in ps
    assert "[ref]$lua_result" in ps
    assert "RSTD.NetStart()" in ps
