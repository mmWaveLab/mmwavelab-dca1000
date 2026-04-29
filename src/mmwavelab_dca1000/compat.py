from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import DCA1000Config
from .ti_cli import TiDcaCli


@dataclass
class SuiteReport:
    output_dir: str
    dca_json: str
    cli_json: str
    results: list[dict]
    files: list[dict]
    passed: bool


class DCA1000CompatibilitySuite:
    def __init__(self, ti_cli: TiDcaCli) -> None:
        self.ti_cli = ti_cli

    def run(
        self,
        *,
        template_json: str | Path,
        output_dir: str | Path,
        duration_ms: int = 1000,
        file_prefix: str = "dca_compat_adc",
    ) -> SuiteReport:
        out = Path(output_dir)
        (out / "data").mkdir(parents=True, exist_ok=True)
        (out / "meta").mkdir(parents=True, exist_ok=True)
        cfg = DCA1000Config.load(template_json)
        cfg.set_capture_path(file_base_path=(out / "data").resolve(), file_prefix=file_prefix, duration_ms=duration_ms)
        runtime_json = cfg.save(out / "meta" / "dca1000_runtime_config.json")
        cli_json = cfg.stage_for_ti_cli(self.ti_cli.exe)

        commands = [
            "query_sys_status",
            "reset_fpga",
            "fpga_version",
            "fpga",
            "fpga_version",
            "record",
            "start_record",
            "query_status",
            "stop_record",
            "query_status",
        ]
        results = []
        for command in commands:
            if command == "start_record":
                timeout_s = max(5.0, duration_ms / 1000.0 + 5.0)
            else:
                timeout_s = 20.0
            result = self.ti_cli.run(command, cli_json, timeout_s=timeout_s)
            results.append(asdict(result))
            time.sleep(0.25)
        for cleanup in self.ti_cli.cleanup_record_helpers():
            results.append(asdict(cleanup))

        files = [
            {"path": str(path), "size_bytes": path.stat().st_size}
            for path in sorted((out / "data").glob("*"))
            if path.is_file()
        ]
        required = {"query_sys_status", "reset_fpga", "fpga", "record", "start_record"}
        passed = all(item["ok"] for item in results if item["command"] in required)
        report = SuiteReport(str(out), str(runtime_json), str(cli_json), results, files, passed)
        (out / "meta" / "dca1000_compat_report.json").write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report
