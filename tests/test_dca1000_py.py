from __future__ import annotations

import struct

from mmwavelab_dca1000.config import DCA1000Config
from mmwavelab_dca1000.dca1000_py import (
    CMD_CONFIG_FPGA,
    CMD_SYSTEM_CONNECT,
    Dca1000Py,
    _build_command,
    _parse_response,
)


def test_build_command_uses_ti_header_and_footer():
    packet = _build_command(CMD_SYSTEM_CONNECT)
    assert packet == struct.pack("<HHHH", 0xA55A, CMD_SYSTEM_CONNECT, 0, 0xEEAA)


def test_parse_response_extracts_status():
    response = struct.pack("<HHHH", 0xA55A, CMD_CONFIG_FPGA, 0, 0xEEAA)
    assert _parse_response(response) == (CMD_CONFIG_FPGA, 0)


def test_from_config_reads_ethernet_ports():
    cfg = DCA1000Config(
        {
            "DCA1000Config": {
                "ethernetConfig": {
                    "DCA1000IPAddress": "192.168.33.180",
                    "DCA1000ConfigPort": 4096,
                    "DCA1000DataPort": 4098,
                },
                "ethernetConfigUpdate": {"systemIPAddress": "192.168.33.30"},
            }
        }
    )
    dca = Dca1000Py.from_config(cfg)
    assert dca.host_ip == "192.168.33.30"
    assert dca.dca_ip == "192.168.33.180"
    assert dca.config_port == 4096
    assert dca.data_port == 4098
