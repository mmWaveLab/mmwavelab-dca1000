from __future__ import annotations

import os
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

    record_helper_names = ("DCA1000EVM_CLI_Record.exe",)

    def __init__(self, exe: str | Path | None = None, *, hide_window: bool = True) -> None:
        resolved = Path(exe) if exe else find_ti_dca_cli()
        if resolved is None:
            raise FileNotFoundError("DCA1000EVM_CLI_Control.exe was not found")
        self.exe = resolved.resolve()
        self.hide_window = hide_window

    def run(self, command: str, config_json: str | Path, timeout_s: float = 20.0) -> TiDcaResult:
        started = time.time()
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                [str(self.exe), command, str(config_json)],
                cwd=str(self.exe.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                **self._window_kwargs(),
            )
            stdout, stderr = process.communicate(timeout=timeout_s)
            output = ((stdout or "") + (("\n" + stderr) if stderr else "")).strip()
            returncode = process.returncode
            return TiDcaResult(
                command=command,
                returncode=returncode,
                output=output,
                duration_s=time.time() - started,
                ok=self._is_ok(command, returncode, output),
            )
        except subprocess.TimeoutExpired as exc:
            if process is not None:
                self._kill_pid_tree(process.pid)
                try:
                    stdout, stderr = process.communicate(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
            else:
                stdout, stderr = exc.stdout, exc.stderr
            output = ((stdout or "") + (("\n" + stderr) if stderr else "")).strip()
            return TiDcaResult(
                command,
                None,
                output or "timeout",
                time.time() - started,
                self._is_ok(command, None, output),
            )

    def cleanup_record_helpers(self) -> list[TiDcaResult]:
        """Terminate TI record helper consoles that can outlive start_record.

        The official CLI sometimes leaves DCA1000EVM_CLI_Record.exe visible
        when no LVDS stream arrives. We only target that helper name.
        """

        if os.name != "nt":
            return []
        results: list[TiDcaResult] = []
        for helper in self.record_helper_names:
            started = time.time()
            completed = subprocess.run(
                ["taskkill", "/IM", helper, "/F", "/T"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                **self._window_kwargs(),
            )
            output = ((completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")).strip()
            ok = completed.returncode in (0, 128) or "not found" in output.lower() or "没有找到" in output
            results.append(TiDcaResult(f"cleanup:{helper}", completed.returncode, output, time.time() - started, ok))
        return results

    def _window_kwargs(self) -> dict:
        if os.name != "nt" or not self.hide_window:
            return {}
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        return {
            "startupinfo": startupinfo,
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        }

    def _kill_pid_tree(self, pid: int) -> TiDcaResult | None:
        if os.name != "nt":
            return None
        started = time.time()
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            **self._window_kwargs(),
        )
        output = ((completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")).strip()
        return TiDcaResult(f"kill_pid_tree:{pid}", completed.returncode, output, time.time() - started, completed.returncode in (0, 128))

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
