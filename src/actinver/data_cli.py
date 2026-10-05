"""Command-line interface for the M2 point-in-time data engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .data_engine import (
    DataEngineError,
    build_dataset,
    query_as_of,
    read_dataset,
    require_fresh_price_bars,
    verify_manifest,
)


ROOT = Path(__file__).resolve().parents[2]


def _json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-data")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="archive and normalize a licensed source file")
    ingest.add_argument("--input", type=Path, required=True)
    ingest.add_argument("--source-id", required=True)
    ingest.add_argument("--publisher", required=True)
    ingest.add_argument("--source-url")
    ingest.add_argument("--license-id", required=True)
    ingest.add_argument("--license-url")
    ingest.add_argument(
        "--redistribution-status",
        choices=("permitted", "restricted", "unknown"),
        required=True,
    )
    ingest.add_argument("--ingestion-time", required=True, help="ISO-8601 timestamp with timezone")
    ingest.add_argument("--code-commit-sha", required=True)
    ingest.add_argument("--project-root", type=Path, default=ROOT)

    verify = commands.add_parser("verify", help="verify raw/interim/processed hashes in a manifest")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--project-root", type=Path, default=ROOT)

    query = commands.add_parser("query", help="reconstruct the latest known records at a timestamp")
    query.add_argument("--manifest", type=Path, required=True)
    query.add_argument("--as-of", required=True, help="ISO-8601 timestamp with timezone")
    query.add_argument("--mode", choices=("source", "system"), default="source")
    query.add_argument(
        "--max-price-age-seconds",
        type=int,
        help="fail closed if any returned price bar is older than this age",
    )
    query.add_argument(
        "--expected-instrument",
        action="append",
        default=None,
        help="required instrument_id for freshness coverage; repeat for each instrument",
    )
    query.add_argument("--project-root", type=Path, default=ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "ingest":
            manifest = build_dataset(
                args.input,
                args.project_root,
                source_id=args.source_id,
                publisher=args.publisher,
                source_url=args.source_url,
                license_id=args.license_id,
                license_url=args.license_url,
                redistribution_status=args.redistribution_status,
                ingestion_time=args.ingestion_time,
                code_commit_sha=args.code_commit_sha,
            )
            _json(
                {
                    "status": "PASS",
                    "dataset_id": manifest["dataset_id"],
                    "manifest_path": f"data/metadata/datasets/{manifest['dataset_id']}.json",
                    "records": manifest["records"],
                    "raw_sha256": manifest["raw_snapshot"]["sha256"],
                }
            )
        elif args.command == "verify":
            _json(verify_manifest(args.manifest, args.project_root))
        elif args.command == "query":
            if args.expected_instrument and args.max_price_age_seconds is None:
                raise DataEngineError(
                    "--expected-instrument requires --max-price-age-seconds"
                )
            manifest, records = read_dataset(args.manifest, args.project_root)
            result = query_as_of(records, args.as_of, mode=args.mode)
            freshness = None
            if args.max_price_age_seconds is not None:
                freshness = require_fresh_price_bars(
                    result,
                    args.as_of,
                    max_age_seconds=args.max_price_age_seconds,
                    mode=args.mode,
                    expected_instrument_ids=args.expected_instrument,
                )
            _json(
                {
                    "dataset_id": manifest["dataset_id"],
                    "as_of": args.as_of,
                    "availability_mode": args.mode,
                    "count": len(result),
                    "price_freshness": freshness,
                    "records": result,
                }
            )
        else:  # pragma: no cover - argparse enforces known commands
            raise DataEngineError(f"Unknown command: {args.command}")
    except (DataEngineError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
