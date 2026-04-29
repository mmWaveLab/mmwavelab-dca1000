from __future__ import annotations

from mmwavelab_dca1000.serial_diag import D2xxNode, DosDeviceMapping, PortOpenAttempt, _build_notes


def test_build_notes_identifies_mapped_denied_ports():
    notes = _build_notes(
        [PortOpenAttempt("COM9", "CreateFileW(access=0)", False, "WinError 5")],
        [DosDeviceMapping("COM9", r"\Device\VCP0")],
        [D2xxNode(0, "0x1", 3, "0x0", "0x0", "", "", 3)],
    )
    assert any("COM9" in note for note in notes)
    assert any("D2XX" in note for note in notes)
