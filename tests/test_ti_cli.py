from __future__ import annotations

from mmwavelab_dca1000.ti_cli import TiDcaCli


def test_fpga_version_nonzero_can_be_ok():
    assert TiDcaCli._is_ok("fpga_version", 1154, "FPGA Version : 2.9 [Record]")
    assert TiDcaCli._is_ok("start_record", None, "Start Record command : Success")
    assert not TiDcaCli._is_ok("query_status", 4294963294, "No record process is running")


def test_hide_window_is_default():
    cli = TiDcaCli.__new__(TiDcaCli)
    cli.hide_window = True
    assert isinstance(cli._window_kwargs(), dict)


def test_taskkill_not_found_is_ok(monkeypatch):
    cli = TiDcaCli.__new__(TiDcaCli)
    cli.hide_window = False
    cli.record_helper_names = ("definitely_not_running.exe",)
    results = cli.cleanup_record_helpers()
    assert len(results) == 1
    assert results[0].ok
