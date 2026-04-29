from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from .compat import DCA1000CompatibilitySuite
from .radar_cli import list_serial_ports, probe_mmwave_cli
from .radar_config import write_iwr1843_best_range_config
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


def cmd_generate_iwr1843_config(args: argparse.Namespace) -> int:
    metrics = write_iwr1843_best_range_config(args.output)
    print(json.dumps(metrics.as_dict(), ensure_ascii=False, indent=2))
    return 0


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

    p = sub.add_parser("generate-iwr1843-config")
    p.add_argument("--output", default="configs/iwr1843_best_range_1tx_256s_3983mhz.cfg")
    p.set_defaults(func=cmd_generate_iwr1843_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
