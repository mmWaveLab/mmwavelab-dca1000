from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TOOL_CANDIDATES = (
    Path(r"C:\ti\radar_toolbox_4_00_00_05\tools\Adc_Data_Capture_Tool_DCA1000_CLI\DCA1000EVM_CLI_Control.exe"),
    Path(r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\PostProc\DCA1000EVM_CLI_Control.exe"),
)


@dataclass
class TiDcaResult:
    command: str
    returncode: int | None
    output: str
    duration_s: float
    ok: bool


def find_ti_dca_cli(extra: list[str | Path] | None = None) -> Path | None:
    candidates = [Path(p) for p in (extra or [])] + list(DEFAULT_TOOL_CANDIDATES)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    ti = Path(r"C:\ti")
    if ti.exists():
        matches = sorted(ti.glob(r"**\DCA1000EVM_CLI_Control.exe"))
        if matches:
            return matches[0]
    return None


class TiDcaCli:
    """Small structured wrapper around TI's DCA1000EVM_CLI_Control.exe."""

    def __init__(self, exe: str | Path | None = None) -> None:
        resolved = Path(exe) if exe else find_ti_dca_cli()
        if resolved is None:
            raise FileNotFoundError("DCA1000EVM_CLI_Control.exe was not found")
        self.exe = resolved.resolve()

    def run(self, command: str, config_json: str | Path, timeout_s: float = 20.0) -> TiDcaResult:
        started = time.time()
        try:
            completed = subprocess.run(
                [str(self.exe), command, str(config_json)],
                cwd=str(self.exe.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
            output = ((completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")).strip()
            return TiDcaResult(
                command=command,
                returncode=completed.returncode,
                output=output,
                duration_s=time.time() - started,
                ok=self._is_ok(command, completed.returncode, output),
            )
        except subprocess.TimeoutExpired as exc:
            output = ((exc.stdout or "") + (("\n" + exc.stderr) if exc.stderr else "")).strip()
            return TiDcaResult(
                command,
                None,
                output or "timeout",
                time.time() - started,
                self._is_ok(command, None, output),
            )

    @staticmethod
    def _is_ok(command: str, returncode: int | None, output: str) -> bool:
        if "Success" in output:
            return True
        if returncode == 0:
            return True
        # TI's tool reports a useful version string with a non-zero exit code.
        if command == "fpga_version" and "FPGA Version" in output:
            return True
        return False
