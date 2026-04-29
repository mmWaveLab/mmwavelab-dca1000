from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from .compat import DCA1000CompatibilitySuite
from .config import DCA1000Config
from .radar_cli import list_serial_ports, load_cli_config_lines, probe_mmwave_cli, send_mmwave_cli_commands
from .radar_config import write_iwr1843_best_range_config
from .rstd import DEFAULT_RSTD_DLL, run_rstd_lua_script
from .serial_diag import collect_serial_diagnostics
from .studio_lua import StudioLuaConfig, write_iwr1843_studio_lua
from .ti_cli import TiDcaCli, find_ti_dca_cli


def cmd_find_tool(_args: argparse.Namespace) -> int:
    tool = find_ti_dca_cli()
    print(tool or "")
    return 0 if tool else 1


def cmd_dca_suite(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir or Path("captures") / f"dca_suite_{time.strftime('%Y%m%d_%H%M%S')}")
    suite = DCA1000CompatibilitySuite(TiDcaCli(args.tool))
    report = suite.run(template_json=args.dca_json, output_dir=output_dir, duration_ms=args.duration_ms)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


def cmd_probe_radar_cli(args: argparse.Namespace) -> int:
    ports = args.ports
    if not ports:
        ports = [str(row["device"]) for row in list_serial_ports() if str(row["device"]).upper().startswith("COM")]
    probes = []
    for port in ports:
        for baudrate in args.baudrate:
            probes.append(asdict(probe_mmwave_cli(port, baudrate=baudrate)))
    print(json.dumps(probes, ensure_ascii=False, indent=2))
    return 0 if any(item["responsive"] for item in probes) else 1


def cmd_serial_diagnostics(args: argparse.Namespace) -> int:
    report = collect_serial_diagnostics(args.ports or None, d2xx_dll=args.d2xx_dll)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if any(item.ok for item in report.open_attempts) else 1


def cmd_generate_iwr1843_config(args: argparse.Namespace) -> int:
    metrics = write_iwr1843_best_range_config(args.output)
    print(json.dumps(metrics.as_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_capture_sdk_demo(args: argparse.Namespace) -> int:
    out = Path(args.output_dir or Path("captures") / f"sdk_demo_capture_{time.strftime('%Y%m%d_%H%M%S')}")
    data_dir = out / "data"
    meta_dir = out / "meta"
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    cfg_lines = load_cli_config_lines(args.radar_cfg, include_sensor_start=False)
    pre_start = [line for line in cfg_lines if line.lower() != "sensorstart"]
    config_result = send_mmwave_cli_commands(
        args.com_port,
        pre_start,
        baudrate=args.baudrate,
        timeout_s=args.command_timeout_s,
        inter_command_delay_s=args.inter_command_delay_s,
    )

    ti = TiDcaCli(args.tool)
    dca_results = []
    start_record_result = None
    start_result = None
    stop_result = None
    if config_result.ok:
        dca_cfg = DCA1000Config.load(args.dca_json)
        dca_cfg.set_capture_path(file_base_path=data_dir.resolve(), file_prefix=args.file_prefix, duration_ms=args.duration_ms)
        runtime_json = dca_cfg.save(meta_dir / "dca1000_runtime_config.json")
        cli_json = dca_cfg.stage_for_ti_cli(ti.exe, "_mmwl_dca1000_runtime_capture.json")
        for command in ("query_sys_status", "reset_fpga", "fpga_version", "fpga", "record"):
            result = ti.run(command, cli_json, timeout_s=20.0)
            dca_results.append(asdict(result))
            if not result.ok and command in {"query_sys_status", "reset_fpga", "fpga", "record"}:
                break
        else:
            record_process = ti.start_process("start_record", cli_json)
            time.sleep(args.record_arm_delay_s)
            start_result = send_mmwave_cli_commands(
                args.com_port,
                ["sensorStart"],
                baudrate=args.baudrate,
                timeout_s=args.command_timeout_s,
            )
            start_record_result = ti.wait_process(
                "start_record",
                record_process,
                timeout_s=max(35.0, args.duration_ms / 1000.0 + 35.0),
            )
            dca_results.append(asdict(start_record_result))
            if args.stop_sensor:
                stop_result = send_mmwave_cli_commands(
                    args.com_port,
                    ["sensorStop"],
                    baudrate=args.baudrate,
                    timeout_s=args.command_timeout_s,
                )
            dca_results.extend(asdict(item) for item in ti.cleanup_record_helpers())
    else:
        runtime_json = None
        cli_json = None

    report = {
        "output_dir": str(out),
        "radar_cfg": str(args.radar_cfg),
        "dca_json": str(runtime_json) if runtime_json else None,
        "cli_json": str(cli_json) if cli_json else None,
        "com_port": args.com_port,
        "baudrate": args.baudrate,
        "config_result": asdict(config_result),
        "dca_results": dca_results,
        "sensor_start": asdict(start_result) if start_result else None,
        "sensor_stop": asdict(stop_result) if stop_result else None,
        "files": [
            {"path": str(path), "size_bytes": path.stat().st_size}
            for path in sorted(out.glob("**/*"))
            if path.is_file()
        ],
    }
    (out / "sdk_demo_capture_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    data_files = [item for item in report["files"] if str(item["path"]).lower().endswith(".bin") and item["size_bytes"] > 0]
    return 0 if data_files else 1


def cmd_generate_studio_lua(args: argparse.Namespace) -> int:
    cfg = StudioLuaConfig(
        com_port=args.com_port,
        baudrate=args.baudrate,
        connect_timeout_ms=args.connect_timeout_ms,
        sop_control=args.sop_control,
        power_on_mode=args.power_on_mode,
        mmwave_studio_root=args.mmwave_studio_root,
        capture_path=args.capture_path,
        host_ip=args.host_ip,
        dca_ip=args.dca_ip,
        dca_mac=args.dca_mac,
        config_port=args.config_port,
        data_port=args.data_port,
        packet_delay_us=args.packet_delay_us,
        frame_count=args.frame_count,
        chirp_loops=args.chirp_loops,
    )
    written = write_iwr1843_studio_lua(args.output, cfg)
    print(json.dumps({"output": str(Path(args.output)), "config": written.as_dict(), "metrics": written.metrics()}, ensure_ascii=False, indent=2))
    return 0


def cmd_run_studio_lua(args: argparse.Namespace) -> int:
    result = run_rstd_lua_script(
        args.script,
        dll_path=args.rstd_dll,
        host=args.host,
        port=args.port,
        timeout_s=args.timeout_s,
    )
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mmwl-dca1000")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("find-tool")
    p.set_defaults(func=cmd_find_tool)

    p = sub.add_parser("dca-suite")
    p.add_argument("--dca-json", default="configs/dca1000_iwr1843.json")
    p.add_argument("--tool", default=None)
    p.add_argument("--output-dir", default="")
    p.add_argument("--duration-ms", type=int, default=1000)
    p.set_defaults(func=cmd_dca_suite)

    p = sub.add_parser("probe-radar-cli")
    p.add_argument("ports", nargs="*")
    p.add_argument("--baudrate", type=int, action="append", default=[115200, 921600])
    p.set_defaults(func=cmd_probe_radar_cli)

    p = sub.add_parser("serial-diagnostics")
    p.add_argument("ports", nargs="*")
    p.add_argument("--d2xx-dll", default=None)
    p.set_defaults(func=cmd_serial_diagnostics)

    p = sub.add_parser("generate-iwr1843-config")
    p.add_argument("--output", default="configs/iwr1843_best_range_1tx_256s_3983mhz.cfg")
    p.set_defaults(func=cmd_generate_iwr1843_config)

    p = sub.add_parser("capture-sdk-demo")
    p.add_argument("--com-port", required=True)
    p.add_argument("--baudrate", type=int, default=115200)
    p.add_argument("--radar-cfg", default="configs/iwr1843_best_range_1tx_256s_3983mhz.cfg")
    p.add_argument("--dca-json", default="configs/dca1000_iwr1843.json")
    p.add_argument("--tool", default=None)
    p.add_argument("--output-dir", default="")
    p.add_argument("--duration-ms", type=int, default=1200)
    p.add_argument("--file-prefix", default="iwr1843_adc")
    p.add_argument("--command-timeout-s", type=float, default=1.5)
    p.add_argument("--inter-command-delay-s", type=float, default=0.05)
    p.add_argument("--record-arm-delay-s", type=float, default=0.5)
    p.add_argument("--stop-sensor", action="store_true")
    p.set_defaults(func=cmd_capture_sdk_demo)

    p = sub.add_parser("generate-studio-lua")
    p.add_argument("--output", default="scripts/iwr1843_dca1000_best_range.lua")
    p.add_argument("--com-port", type=int, default=12)
    p.add_argument("--baudrate", type=int, default=921600)
    p.add_argument("--connect-timeout-ms", type=int, default=1000)
    p.add_argument("--sop-control", type=int, default=2)
    p.add_argument("--power-on-mode", type=int, default=1)
    p.add_argument("--mmwave-studio-root", default=r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio")
    p.add_argument("--capture-path", default=r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\PostProc\adc_data.bin")
    p.add_argument("--host-ip", default="192.168.33.30")
    p.add_argument("--dca-ip", default="192.168.33.180")
    p.add_argument("--dca-mac", default="12:34:56:78:90:12")
    p.add_argument("--config-port", type=int, default=4096)
    p.add_argument("--data-port", type=int, default=4098)
    p.add_argument("--packet-delay-us", type=int, default=25)
    p.add_argument("--frame-count", type=int, default=5)
    p.add_argument("--chirp-loops", type=int, default=16)
    p.set_defaults(func=cmd_generate_studio_lua)

    p = sub.add_parser("run-studio-lua")
    p.add_argument("script")
    p.add_argument("--rstd-dll", default=DEFAULT_RSTD_DLL)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2777)
    p.add_argument("--timeout-s", type=int, default=180)
    p.set_defaults(func=cmd_run_studio_lua)

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
