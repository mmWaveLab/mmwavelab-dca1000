from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import serial
from serial.tools import list_ports


@dataclass
class SerialProbe:
    port: str
    baudrate: int
    responsive: bool
    bytes_read: int
    text: str
    error: str = ""


@dataclass
class CliCommandResult:
    command: str
    ok: bool
    bytes_read: int
    text: str
    error: str = ""


@dataclass
class CliConfigResult:
    port: str
    baudrate: int
    commands: list[CliCommandResult]
    ok: bool


def list_serial_ports() -> list[dict[str, str | int | None]]:
    rows = []
    for port in list_ports.comports():
        rows.append(
            {
                "device": port.device,
                "description": port.description,
                "serial_number": port.serial_number,
                "vid": port.vid,
                "pid": port.pid,
                "hwid": port.hwid,
            }
        )
    return rows


def probe_mmwave_cli(port: str, baudrate: int = 115200, timeout_s: float = 2.0) -> SerialProbe:
    try:
        with serial.Serial(port, baudrate=baudrate, timeout=0.05, write_timeout=0.8) as ser:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(b"\r\nversion\r\n")
            ser.flush()
            chunks: list[bytes] = []
            end = time.time() + timeout_s
            while time.time() < end:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    chunks.append(chunk)
                else:
                    time.sleep(0.02)
            raw = b"".join(chunks)
            text = raw.decode("utf-8", errors="replace")
            lowered = text.lower()
            responsive = any(token in lowered for token in ("mmwave sdk", "platform", "xwr", "mmwdemo"))
            return SerialProbe(port, baudrate, responsive, len(raw), text)
    except Exception as exc:
        return SerialProbe(port, baudrate, False, 0, "", f"{type(exc).__name__}: {exc}")


def load_cli_config_lines(path: str | Path, *, include_sensor_start: bool = False) -> list[str]:
    lines: list[str] = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("%") or line.startswith("#"):
            continue
        if not include_sensor_start and line.lower() == "sensorstart":
            continue
        lines.append(line)
    return lines


def send_mmwave_cli_commands(
    port: str,
    commands: list[str],
    *,
    baudrate: int = 115200,
    timeout_s: float = 1.5,
    inter_command_delay_s: float = 0.05,
) -> CliConfigResult:
    results: list[CliCommandResult] = []
    try:
        with serial.Serial(port, baudrate=baudrate, timeout=0.05, write_timeout=1.0) as ser:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            for command in commands:
                result = _send_one_cli_command(ser, command, timeout_s=timeout_s)
                results.append(result)
                time.sleep(inter_command_delay_s)
                if not result.ok:
                    break
    except Exception as exc:
        results.append(CliCommandResult("", False, 0, "", f"{type(exc).__name__}: {exc}"))
    return CliConfigResult(port, baudrate, results, all(item.ok for item in results) and bool(results))


def _send_one_cli_command(ser: serial.Serial, command: str, *, timeout_s: float) -> CliCommandResult:
    try:
        ser.write(command.encode("ascii", errors="replace") + b"\r\n")
        ser.flush()
        chunks: list[bytes] = []
        end = time.time() + timeout_s
        while time.time() < end:
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                chunks.append(chunk)
                text = b"".join(chunks).decode("utf-8", errors="replace")
                lowered = text.lower()
                if "error" in lowered or "exception" in lowered:
                    break
                if "done" in lowered or "mmw" in lowered or "mmwave" in lowered:
                    # The demo CLI usually echoes a prompt/banner after success.
                    if len(text) > len(command):
                        break
            else:
                time.sleep(0.01)
        raw = b"".join(chunks)
        text = raw.decode("utf-8", errors="replace")
        lowered = text.lower()
        ok = "error" not in lowered and "exception" not in lowered
        return CliCommandResult(command, ok, len(raw), text)
    except Exception as exc:
        return CliCommandResult(command, False, 0, "", f"{type(exc).__name__}: {exc}")
