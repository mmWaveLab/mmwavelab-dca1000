from __future__ import annotations

from mmwavelab_dca1000.ti_cli import TiDcaCli


def test_fpga_version_nonzero_can_be_ok():
    assert TiDcaCli._is_ok("fpga_version", 1154, "FPGA Version : 2.9 [Record]")
    assert TiDcaCli._is_ok("start_record", None, "Start Record command : Success")
    assert not TiDcaCli._is_ok("query_status", 4294963294, "No record process is running")
