from __future__ import annotations

import ctypes
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import serial

from .radar_cli import list_serial_ports


@dataclass
class PortOpenAttempt:
    port: str
    method: str
    ok: bool
    error: str = ""


@dataclass
class DosDeviceMapping:
    port: str
    target: str
    error: str = ""


@dataclass
class D2xxNode:
    index: int
    flags: str
    device_type: int
    device_id: str
    loc_id: str
    serial: str
    description: str
    open_status: int | None


@dataclass
class SerialDiagnostics:
    serial_ports: list[dict]
    dos_devices: list[DosDeviceMapping]
    open_attempts: list[PortOpenAttempt]
    d2xx_nodes: list[D2xxNode]
    notes: list[str]

    def as_dict(self) -> dict:
        return {
            "serial_ports": self.serial_ports,
            "dos_devices": [asdict(item) for item in self.dos_devices],
            "open_attempts": [asdict(item) for item in self.open_attempts],
            "d2xx_nodes": [asdict(item) for item in self.d2xx_nodes],
            "notes": self.notes,
        }


def collect_serial_diagnostics(ports: list[str] | None = None, *, d2xx_dll: str | Path | None = None) -> SerialDiagnostics:
    serial_ports = list_serial_ports()
    if ports is None:
        ports = sorted({str(row["device"]) for row in serial_ports if str(row["device"]).upper().startswith("COM")})

    dos_devices = [_query_dos_device(port) for port in ports]
    open_attempts: list[PortOpenAttempt] = []
    for port in ports:
        open_attempts.append(_try_pyserial(port))
        if os.name == "nt":
            open_attempts.append(_try_create_file(port))

    nodes: list[D2xxNode] = []
    if os.name == "nt":
        dll = Path(d2xx_dll) if d2xx_dll else Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "ftd2xx.dll"
        if dll.exists():
            nodes = _probe_d2xx(dll)

    notes = _build_notes(open_attempts, dos_devices, nodes)
    return SerialDiagnostics(serial_ports, dos_devices, open_attempts, nodes, notes)


def _query_dos_device(port: str) -> DosDeviceMapping:
    if os.name != "nt":
        return DosDeviceMapping(port, "")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel32.QueryDosDeviceW
    query.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    query.restype = ctypes.c_uint32
    buf = ctypes.create_unicode_buffer(4096)
    n = query(port, buf, len(buf))
    if n:
        return DosDeviceMapping(port, buf.value)
    return DosDeviceMapping(port, "", f"WinError {ctypes.get_last_error()}")


def _try_pyserial(port: str) -> PortOpenAttempt:
    try:
        with serial.Serial(port, baudrate=115200, timeout=0.05, write_timeout=0.2):
            return PortOpenAttempt(port, "pyserial", True)
    except Exception as exc:
        return PortOpenAttempt(port, "pyserial", False, f"{type(exc).__name__}: {exc}")


def _try_create_file(port: str) -> PortOpenAttempt:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    invalid = ctypes.c_void_p(-1).value
    handle = create_file(rf"\\.\{port}", 0, 0x00000001 | 0x00000002, None, 3, 0, None)
    if handle == invalid:
        return PortOpenAttempt(port, "CreateFileW(access=0)", False, f"WinError {ctypes.get_last_error()}")
    close_handle(handle)
    return PortOpenAttempt(port, "CreateFileW(access=0)", True)


def _probe_d2xx(dll_path: Path) -> list[D2xxNode]:
    try:
        dll = ctypes.WinDLL(str(dll_path))
    except Exception:
        return []

    dword = ctypes.c_ulong

    class Node(ctypes.Structure):
        _fields_ = [
            ("Flags", dword),
            ("Type", dword),
            ("ID", dword),
            ("LocId", dword),
            ("SerialNumber", ctypes.c_char * 16),
            ("Description", ctypes.c_char * 64),
            ("ftHandle", ctypes.c_void_p),
        ]

    num = dword(0)
    if dll.FT_CreateDeviceInfoList(ctypes.byref(num)) != 0 or num.value == 0:
        return []
    arr = (Node * num.value)()
    if dll.FT_GetDeviceInfoList(arr, ctypes.byref(num)) != 0:
        return []

    out: list[D2xxNode] = []
    for idx, node in enumerate(arr):
        handle = ctypes.c_void_p()
        try:
            open_status = int(dll.FT_Open(idx, ctypes.byref(handle)))
            if open_status == 0:
                dll.FT_Close(handle)
        except Exception:
            open_status = None
        out.append(
            D2xxNode(
                idx,
                hex(int(node.Flags)),
                int(node.Type),
                hex(int(node.ID)),
                hex(int(node.LocId)),
                bytes(node.SerialNumber).split(b"\0", 1)[0].decode("ascii", errors="replace"),
                bytes(node.Description).split(b"\0", 1)[0].decode("ascii", errors="replace"),
                open_status,
            )
        )
    return out


def _build_notes(open_attempts: list[PortOpenAttempt], dos_devices: list[DosDeviceMapping], nodes: list[D2xxNode]) -> list[str]:
    notes: list[str] = []
    denied = [item.port for item in open_attempts if not item.ok and ("WinError 5" in item.error or "PermissionError" in item.error)]
    if denied:
        notes.append("One or more COM devices reject even attribute-only opens. This is usually a driver/security/lock state, not a radar protocol timeout.")
    mapped_but_denied = sorted({item.port for item in open_attempts if not item.ok} & {item.port for item in dos_devices if item.target})
    if mapped_but_denied:
        notes.append(f"Ports have DOS device mappings but cannot be opened: {', '.join(mapped_but_denied)}.")
    if nodes and all(node.open_status not in (0, None) for node in nodes):
        notes.append("D2XX enumerates FTDI nodes but FT_Open fails for every node; try a physical USB replug or elevated FTDI driver restart/reinstall.")
    return notes
