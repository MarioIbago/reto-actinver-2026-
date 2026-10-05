"""Command line workflows for M9 operator reports and audit records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .trade_sheet import (
    TradeSheetError,
    create_post_trade_attribution,
    create_trade_sheet,
    read_json,
    verify_audit_log,
)


def _path(value: Path) -> Path:
    return value.resolve()


def _write_stdout(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="actinver-cockpit",
        description="Build human-reviewed Actinver reports; never submits orders.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    report = commands.add_parser("report", help="create a morning, event-update, or evening report")
    report.add_argument("--type", choices=("morning", "event_update", "evening_review"), required=True)
    report.add_argument("--context", type=Path, required=True, help="versioned tournament/portfolio context JSON")
    report.add_argument("--m7-result", type=Path, help="exact M7 result JSON for provenance")
    report.add_argument("--m8-result", type=Path, help="exact M8 result JSON; its M7 byte hash is checked")
    report.add_argument("--event-snapshot", type=Path, action="append", default=[], help="validated M6 event snapshot; repeatable")
    report.add_argument("--output-dir", type=Path, default=Path("reports/trade_sheets"))
    report.add_argument("--audit-file", type=Path, default=Path("reports/audit_trail/m9.jsonl"))

    verify = commands.add_parser("verify-audit", help="verify every event and hash link in the append-only JSONL trail")
    verify.add_argument("--audit-file", type=Path, default=Path("reports/audit_trail/m9.jsonl"))

    attribution = commands.add_parser("attribute", help="create descriptive post-activity attribution from manual records")
    attribution.add_argument("--activity", type=Path, required=True, help="operator-entered balance and manual fill JSON")
    attribution.add_argument("--trade-sheet", type=Path, required=True, help="linked M9 report JSON")
    attribution.add_argument("--output", type=Path, required=True, help="new attribution JSON path")
    attribution.add_argument("--audit-file", type=Path, default=Path("reports/audit_trail/m9.jsonl"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "report":
            context, context_bytes = read_json(_path(args.context))
            if args.m7_result is None:
                m7_result, m7_sha = None, None
            else:
                m7_result, raw_m7 = read_json(_path(args.m7_result))
                m7_sha = hashlib.sha256(raw_m7).hexdigest()
            if args.m8_result is None:
                m8_result, m8_sha = None, None
            else:
                m8_result, raw_m8 = read_json(_path(args.m8_result))
                m8_sha = hashlib.sha256(raw_m8).hexdigest()
            event_inputs = [read_json(_path(path)) for path in args.event_snapshot]
            event_snapshots = [value for value, _raw in event_inputs]
            event_sha256 = [hashlib.sha256(raw).hexdigest() for _value, raw in event_inputs]
            report, report_path, audit_event = create_trade_sheet(
                context,
                report_type=args.type,
                output_dir=_path(args.output_dir),
                audit_path=_path(args.audit_file),
                m7_result=m7_result,
                m7_sha256=m7_sha,
                m8_result=m8_result,
                m8_sha256=m8_sha,
                event_snapshots=event_snapshots,
                context_sha256=hashlib.sha256(context_bytes).hexdigest(),
                event_snapshot_sha256=event_sha256,
            )
            _write_stdout({
                "report_id": report["report_id"],
                "report_path": str(report_path),
                "decision_status": report["decision_status"],
                "audit_event_sha256": audit_event["event_sha256"],
                "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            })
            return 0

        if args.command == "verify-audit":
            result = verify_audit_log(_path(args.audit_file))
            _write_stdout(result)
            return 0

        if args.command == "attribute":
            activity, _activity_bytes = read_json(_path(args.activity))
            trade_sheet, sheet_bytes = read_json(_path(args.trade_sheet))
            _attribution, event = create_post_trade_attribution(
                activity,
                trade_sheet,
                output_path=_path(args.output),
                audit_path=_path(args.audit_file),
                report_sha256=hashlib.sha256(sheet_bytes).hexdigest(),
            )
            _write_stdout({
                "attribution_id": _attribution["attribution_id"],
                "output_path": str(_path(args.output)),
                "attribution_status": _attribution["attribution_status"],
                "audit_event_sha256": event["event_sha256"],
                "attribution_sha256": hashlib.sha256(_path(args.output).read_bytes()).hexdigest(),
            })
            return 0

        raise TradeSheetError(f"unknown command: {args.command}")
    except (TradeSheetError, OSError, TypeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
