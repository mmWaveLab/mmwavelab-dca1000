from __future__ import annotations

import json

from mmwavelab_dca1000.config import DCA1000Config


def test_save_json_has_no_utf8_bom(tmp_path):
    cfg = DCA1000Config({"DCA1000Config": {"captureConfig": {}}})
    path = cfg.save(tmp_path / "dca.json")
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8"))["DCA1000Config"]


def test_set_capture_path(tmp_path):
    cfg = DCA1000Config({"DCA1000Config": {}})
    cfg.set_capture_path(file_base_path=tmp_path / "data", file_prefix="x", duration_ms=250)
    capture = cfg.data["DCA1000Config"]["captureConfig"]
    assert capture["filePrefix"] == "x"
    assert capture["durationToCapture_ms"] == 250
