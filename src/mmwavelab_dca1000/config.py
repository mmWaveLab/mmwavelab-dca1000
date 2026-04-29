from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DCA1000Config:
    """Mutable wrapper around TI's DCA1000 JSON schema."""

    data: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "DCA1000Config":
        return cls(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    def clone(self) -> "DCA1000Config":
        return DCA1000Config(json.loads(json.dumps(self.data)))

    @property
    def root(self) -> dict[str, Any]:
        return self.data.setdefault("DCA1000Config", {})

    def set_capture_path(
        self,
        *,
        file_base_path: str | Path,
        file_prefix: str = "adc_data",
        duration_ms: int | None = None,
        stop_mode: str = "duration",
    ) -> None:
        capture = self.root.setdefault("captureConfig", {})
        capture["fileBasePath"] = str(Path(file_base_path))
        capture["filePrefix"] = file_prefix
        capture["captureStopMode"] = stop_mode
        if duration_ms is not None:
            capture["durationToCapture_ms"] = int(duration_ms)

    def set_ethernet(
        self,
        *,
        host_ip: str = "192.168.33.30",
        dca_ip: str = "192.168.33.180",
        config_port: int = 4096,
        data_port: int = 4098,
        mac: str = "12.34.56.78.90.12",
    ) -> None:
        eth = self.root.setdefault("ethernetConfig", {})
        eth["DCA1000IPAddress"] = dca_ip
        eth["DCA1000ConfigPort"] = int(config_port)
        eth["DCA1000DataPort"] = int(data_port)
        update = self.root.setdefault("ethernetConfigUpdate", {})
        update["systemIPAddress"] = host_ip
        update["DCA1000IPAddress"] = dca_ip
        update["DCA1000MACAddress"] = mac
        update["DCA1000ConfigPort"] = int(config_port)
        update["DCA1000DataPort"] = int(data_port)

    def save(self, path: str | Path) -> Path:
        """Save as UTF-8 without BOM.

        TI's CLI rejects BOM-prefixed JSON, so never use PowerShell's legacy
        UTF8 writer for runtime configs.
        """

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return target

    def stage_for_ti_cli(self, ti_cli_exe: str | Path, name: str = "_mmwl_dca1000_runtime.json") -> Path:
        """Copy JSON next to TI's CLI to avoid long-path parsing bugs."""

        staged = Path(ti_cli_exe).resolve().parent / name
        tmp = staged.with_suffix(".tmp.json")
        self.save(tmp)
        shutil.move(str(tmp), staged)
        return staged
