from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_RSTD_DLL = r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\Clients\RtttNetClientController\RtttNetClientAPI.dll"


@dataclass(frozen=True)
class RstdCommandResult:
    command: str
    returncode: int
    output: str
    ok: bool

    def as_dict(self) -> dict[str, str | int | bool]:
        return asdict(self)


def _ps_single_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _lua_string(value: str | Path) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def build_rstd_powershell_command(
    lua_command: str,
    *,
    dll_path: str | Path = DEFAULT_RSTD_DLL,
    host: str = "127.0.0.1",
    port: int = 2777,
) -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"Add-Type -Path {_ps_single_quote(dll_path)}",
            "$init = [RtttNetClientAPI.RtttNetClient]::Init()",
            '"Init=" + $init',
            f"$connect = [RtttNetClientAPI.RtttNetClient]::Connect({_ps_single_quote(host)}, {port})",
            '"Connect=" + $connect',
            "if ($connect -ne 0) {",
            "  Write-Output 'Unable to connect to mmWave Studio RSTD net server. In the Studio Lua shell run: RSTD.NetStart()'",
            "  exit 2",
            "}",
            "$lua_result = New-Object 'System.Object[]' 0",
            f"$send = [RtttNetClientAPI.RtttNetClient]::SendCommand({_ps_single_quote(lua_command)}, [ref]$lua_result)",
            '"SendCommand=" + $send',
            "if ($send -ne 30000) { exit 3 }",
        ]
    )


def build_dofile_command(script_path: str | Path) -> str:
    return f"dofile({_lua_string(Path(script_path).resolve())})"


def run_rstd_lua_command(
    lua_command: str,
    *,
    dll_path: str | Path = DEFAULT_RSTD_DLL,
    host: str = "127.0.0.1",
    port: int = 2777,
    timeout_s: int = 180,
) -> RstdCommandResult:
    ps = build_rstd_powershell_command(lua_command, dll_path=dll_path, host=host, port=port)
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = ((exc.stdout or "") + (exc.stderr or "")).strip()
        output = f"Timed out after {timeout_s}s while waiting for mmWave Studio. Partial output: {partial}"
        return RstdCommandResult(command=lua_command, returncode=124, output=output, ok=False)
    output = (completed.stdout + completed.stderr).strip()
    return RstdCommandResult(command=lua_command, returncode=completed.returncode, output=output, ok=completed.returncode == 0)


def run_rstd_lua_script(
    script_path: str | Path,
    *,
    dll_path: str | Path = DEFAULT_RSTD_DLL,
    host: str = "127.0.0.1",
    port: int = 2777,
    timeout_s: int = 180,
) -> RstdCommandResult:
    return run_rstd_lua_command(
        build_dofile_command(script_path),
        dll_path=dll_path,
        host=host,
        port=port,
        timeout_s=timeout_s,
    )
