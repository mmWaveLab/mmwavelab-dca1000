from __future__ import annotations

import time
from dataclasses import dataclass

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
