from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .config import DCA1000Config


HEADER = 0xA55A
FOOTER = 0xEEAA

CMD_RESET_FPGA = 0x01
CMD_RESET_RADAR = 0x02
CMD_CONFIG_FPGA = 0x03
CMD_RECORD_START = 0x05
CMD_RECORD_STOP = 0x06
CMD_SYSTEM_CONNECT = 0x09
CMD_CONFIG_PACKET_DATA = 0x0B
CMD_READ_FPGA_VERSION = 0x0E


@dataclass(frozen=True)
class DcaPyCommandResult:
    command: str
    command_code: int
    status: int | None
    raw_response_hex: str
    ok: bool
    duration_s: float
    error: str = ""

    def as_dict(self) -> dict[str, str | int | bool | float | None]:
        return asdict(self)


@dataclass
class DcaPacketStats:
    packets: int = 0
    payload_bytes: int = 0
    first_sequence: int | None = None
    last_sequence: int | None = None
    out_of_sequence: int = 0
    first_byte_count: int | None = None
    last_byte_count: int | None = None
    stopped_by_timeout: bool = False
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _build_command(command_code: int, payload: bytes = b"") -> bytes:
    return struct.pack("<HHH", HEADER, command_code, len(payload)) + payload + struct.pack("<H", FOOTER)


def _parse_response(data: bytes) -> tuple[int, int] | None:
    if len(data) < 8:
        return None
    header, command_code, status, footer = struct.unpack("<HHHH", data[:8])
    if header != HEADER or footer != FOOTER:
        return None
    return command_code, status


def _u16_version_string(value: int) -> str:
    major = value & 0x7F
    minor = (value >> 7) & 0x7F
    mode = "Playback" if (value & (1 << 14)) else "Record"
    return f"{major}.{minor} [{mode}]"


class Dca1000Py:
    """Pure Python UDP control/data path for DCA1000EVM.

    The command framing follows TI's documented DCA1000 UDP command protocol.
    It deliberately avoids mmWave Studio and DCA1000EVM_CLI_Control.exe.
    """

    def __init__(
        self,
        *,
        host_ip: str = "192.168.33.30",
        dca_ip: str = "192.168.33.180",
        config_port: int = 4096,
        data_port: int = 4098,
        timeout_s: float = 2.0,
    ) -> None:
        self.host_ip = host_ip
        self.dca_ip = dca_ip
        self.config_port = int(config_port)
        self.data_port = int(data_port)
        self.timeout_s = float(timeout_s)

    @classmethod
    def from_config(cls, config: DCA1000Config, *, timeout_s: float = 2.0) -> "Dca1000Py":
        root = config.root
        eth = root.get("ethernetConfig", {})
        update = root.get("ethernetConfigUpdate", {})
        return cls(
            host_ip=str(update.get("systemIPAddress", "192.168.33.30")),
            dca_ip=str(eth.get("DCA1000IPAddress", "192.168.33.180")),
            config_port=int(eth.get("DCA1000ConfigPort", 4096)),
            data_port=int(eth.get("DCA1000DataPort", 4098)),
            timeout_s=timeout_s,
        )

    def send_command(self, name: str, command_code: int, payload: bytes = b"", *, timeout_s: float | None = None) -> DcaPyCommandResult:
        started = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self.timeout_s if timeout_s is None else timeout_s)
        try:
            try:
                sock.bind((self.host_ip, self.config_port))
            except OSError:
                # Some Windows NIC states reject binding the explicit address.
                sock.bind(("", self.config_port))
            sock.sendto(_build_command(command_code, payload), (self.dca_ip, self.config_port))
            response, _addr = sock.recvfrom(2048)
            parsed = _parse_response(response)
            if parsed is None:
                return DcaPyCommandResult(name, command_code, None, response.hex(), False, time.time() - started, "invalid response packet")
            resp_command, status = parsed
            ok = resp_command == command_code and (status == 0 or command_code == CMD_READ_FPGA_VERSION)
            return DcaPyCommandResult(name, command_code, status, response.hex(), ok, time.time() - started)
        except Exception as exc:
            return DcaPyCommandResult(name, command_code, None, "", False, time.time() - started, f"{type(exc).__name__}: {exc}")
        finally:
            sock.close()

    def system_connect(self) -> DcaPyCommandResult:
        return self.send_command("query_sys_status", CMD_SYSTEM_CONNECT)

    def reset_fpga(self) -> DcaPyCommandResult:
        return self.send_command("reset_fpga", CMD_RESET_FPGA)

    def reset_radar(self) -> DcaPyCommandResult:
        return self.send_command("reset_ar_device", CMD_RESET_RADAR)

    def fpga_version(self) -> DcaPyCommandResult:
        result = self.send_command("fpga_version", CMD_READ_FPGA_VERSION)
        if result.status is not None and result.ok:
            return DcaPyCommandResult(
                result.command,
                result.command_code,
                result.status,
                result.raw_response_hex,
                result.ok,
                result.duration_s,
                _u16_version_string(result.status),
            )
        return result

    def config_fpga(
        self,
        *,
        data_logging_mode: int = 1,
        lvds_mode: int = 2,
        data_transfer_mode: int = 1,
        data_capture_mode: int = 2,
        data_format_mode: int = 3,
        timer_s: int = 30,
    ) -> DcaPyCommandResult:
        payload = bytes(
            [
                int(data_logging_mode),
                int(lvds_mode),
                int(data_transfer_mode),
                int(data_capture_mode),
                int(data_format_mode),
                int(timer_s),
            ]
        )
        return self.send_command("fpga", CMD_CONFIG_FPGA, payload)

    def config_packet_data(self, *, packet_size: int = 1472, packet_delay_us: int = 25) -> DcaPyCommandResult:
        payload = struct.pack("<HHH", int(packet_size), int(packet_delay_us), 0)
        return self.send_command("record", CMD_CONFIG_PACKET_DATA, payload)

    def record_start(self) -> DcaPyCommandResult:
        return self.send_command("start_record", CMD_RECORD_START)

    def record_stop(self) -> DcaPyCommandResult:
        return self.send_command("stop_record", CMD_RECORD_STOP)

    def configure_from_json(self, config: DCA1000Config) -> list[DcaPyCommandResult]:
        root = config.root
        results = [self.system_connect(), self.reset_fpga(), self.fpga_version()]
        fpga = self.config_fpga(
            data_logging_mode=_mode_value(root.get("dataLoggingMode", "raw"), {"raw": 1, "multi": 2}, 1),
            lvds_mode=int(root.get("lvdsMode", 2)),
            data_transfer_mode=_mode_value(root.get("dataTransferMode", "LVDSCapture"), {"lvdscapture": 1, "playback": 2}, 1),
            data_capture_mode=_mode_value(root.get("dataCaptureMode", "ethernetStream"), {"sdstorage": 1, "ethernetstream": 2}, 2),
            data_format_mode=int(root.get("dataFormatMode", 3)),
            timer_s=30,
        )
        results.append(fpga)
        packet_delay = int(root.get("packetDelay_us", root.get("captureConfig", {}).get("packetDelay_us", 25)))
        results.append(self.config_packet_data(packet_delay_us=packet_delay))
        return results

    def capture_udp(
        self,
        *,
        raw_udp_path: str | Path,
        adc_payload_path: str | Path,
        duration_s: float,
        strip_sequence_header: bool = True,
        stop_event: threading.Event | None = None,
    ) -> DcaPacketStats:
        raw_path = Path(raw_udp_path)
        payload_path = Path(adc_payload_path)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        stats = DcaPacketStats()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.25)
        try:
            try:
                sock.bind((self.host_ip, self.data_port))
            except OSError:
                sock.bind(("", self.data_port))
            end = time.time() + duration_s
            expected_seq: int | None = None
            with raw_path.open("wb") as raw_file, payload_path.open("wb") as payload_file:
                while time.time() < end and not (stop_event and stop_event.is_set()):
                    try:
                        packet, _addr = sock.recvfrom(9000)
                    except socket.timeout:
                        continue
                    raw_file.write(packet)
                    payload = packet
                    if strip_sequence_header and len(packet) >= 10:
                        seq = int.from_bytes(packet[0:4], "little", signed=False)
                        byte_count = int.from_bytes(packet[4:10] + b"\x00\x00", "little", signed=False)
                        if stats.first_sequence is None:
                            stats.first_sequence = seq
                            stats.first_byte_count = byte_count
                            expected_seq = seq
                        if expected_seq is not None and seq != expected_seq:
                            stats.out_of_sequence += 1
                            expected_seq = seq
                        expected_seq = (expected_seq or seq) + 1
                        stats.last_sequence = seq
                        stats.last_byte_count = byte_count
                        payload = packet[10:]
                    payload_file.write(payload)
                    stats.packets += 1
                    stats.payload_bytes += len(payload)
            stats.stopped_by_timeout = time.time() >= end
        except Exception as exc:
            stats.errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            sock.close()
        return stats


def _mode_value(value: object, lookup: dict[str, int], default: int) -> int:
    if isinstance(value, int):
        return value
    key = str(value).replace("_", "").replace("-", "").lower()
    return lookup.get(key, default)


def summarize_results(results: Iterable[DcaPyCommandResult]) -> list[dict[str, object]]:
    return [result.as_dict() for result in results]
