#!/usr/bin/env python3
"""Build an auditable local M2 dataset from the captured BMV 2026 calendar."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from actinver.data_engine import DataEngineError, build_dataset
from actinver.m1 import M1DataError, load_rules, verify_rule_source_material


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config/actinver_rules.yaml"
CALENDAR_SOURCE_ID = "bmv_holidays_2026"


def canonical_source_bytes(path: Path) -> bytes:
    """Return source bytes with only line endings normalized, matching M1."""
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _git_commit_sha(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def build_calendar_records(ingestion_time: str) -> tuple[list[dict], dict]:
    """Create date-precision events tied to the verified official capture."""
    rules = load_rules(RULES_PATH)
    verify_rule_source_material(rules, ROOT)

    source = next(
        (
            item
            for item in rules["sources"]
            if item.get("source_id") == CALENDAR_SOURCE_ID
        ),
        None,
    )
    if source is None or not source.get("repository_snapshot_path"):
        raise ValueError("The BMV calendar source must reference a preserved source capture")

    capture_path = ROOT / source["repository_snapshot_path"]
    capture_bytes = canonical_source_bytes(capture_path)
    capture_sha256 = hashlib.sha256(capture_bytes).hexdigest()
    if capture_sha256 != source.get("repository_snapshot_sha256"):
        raise ValueError("The BMV calendar capture does not match its configured SHA-256")

    calendar = rules["rules"]["market_calendar"]
    if calendar.get("source_id") != CALENDAR_SOURCE_ID:
        raise ValueError("The configured BMV calendar references a different source")
    timezone_name = rules["rules"]["market_execution_windows"].get("source_timezone")
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ValueError("The BMV execution timezone must be explicit")
    try:
        market_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Timezone database does not contain {timezone_name!r}") from exc

    observed_at = datetime.fromisoformat(source["checked_at_utc"].replace("Z", "+00:00"))
    built_at = datetime.fromisoformat(ingestion_time.replace("Z", "+00:00"))
    if observed_at.tzinfo is None or built_at.tzinfo is None:
        raise ValueError("Source capture and ingestion timestamps must include a timezone")
    if built_at < observed_at:
        raise ValueError("Ingestion time cannot precede the source capture timestamp")

    records = []
    for holiday in calendar["holidays"]:
        event_date = date.fromisoformat(holiday["date"])
        if event_date.year != calendar["year"]:
            raise ValueError("Calendar event year does not match the configured snapshot")
        local_midnight = datetime.combine(event_date, time.min, tzinfo=market_timezone)
        records.append(
            {
                "record_id": f"{calendar['calendar_id']}:{event_date.isoformat()}",
                "instrument_id": f"BMV-CALENDAR-{calendar['year']}",
                "record_type": "calendar_event",
                "event_time": local_midnight.isoformat(),
                # Capture time is the earliest evidenced availability, not a claim
                # about the calendar's original publication time.
                "available_time": source["checked_at_utc"],
                "ingestion_time": ingestion_time,
                "source_id": CALENDAR_SOURCE_ID,
                "source_revision": f"sha256-{capture_sha256}",
                "payload": {
                    "calendar_id": calendar["calendar_id"],
                    "event_date": event_date.isoformat(),
                    "event_name": holiday["name"],
                    "event_status": "market_closed",
                    "event_precision": "date",
                    "event_timezone": timezone_name,
                    "available_time_basis": "first_observed_at_preserved_source_capture",
                    "original_first_publication_time": None,
                    "source_capture_path": source["repository_snapshot_path"],
                    "source_capture_sha256": capture_sha256,
                },
            }
        )

    if not records:
        raise ValueError("The BMV calendar source contains no events")
    return records, source


def build_bmv_calendar_dataset(
    *,
    ingestion_time: str,
    code_commit_sha: str,
    output_root: Path,
) -> dict:
    records, source = build_calendar_records(ingestion_time)
    canonical_jsonl = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for record in records
    )
    with tempfile.TemporaryDirectory(prefix="actinver-bmv-calendar-") as temp_dir:
        input_path = Path(temp_dir) / "bmv_calendar.jsonl"
        input_path.write_text(canonical_jsonl, encoding="utf-8", newline="\n")
        return build_dataset(
            input_path,
            output_root,
            source_id=CALENDAR_SOURCE_ID,
            publisher=source["publisher"],
            source_url=source["url"],
            license_id="unknown-public-web-terms",
            redistribution_status="unknown",
            ingestion_time=ingestion_time,
            code_commit_sha=code_commit_sha,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ingestion-time",
        required=True,
        help="explicit ISO-8601 system ingestion timestamp with timezone",
    )
    parser.add_argument(
        "--code-commit-sha",
        default=None,
        help="full Git SHA; defaults to HEAD of the source repository",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT,
        help="local dataset output root (defaults to this repository)",
    )
    args = parser.parse_args(argv)

    try:
        commit_sha = args.code_commit_sha or _git_commit_sha(ROOT)
        manifest = build_bmv_calendar_dataset(
            ingestion_time=args.ingestion_time,
            code_commit_sha=commit_sha,
            output_root=args.output_root.resolve(),
        )
    except (DataEngineError, M1DataError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": "PASS",
                "dataset_id": manifest["dataset_id"],
                "manifest_path": (
                    Path("data")
                    / "metadata"
                    / "datasets"
                    / f"{manifest['dataset_id']}.json"
                ).as_posix(),
                "record_count": manifest["records"]["unique_version_count"],
                "raw_sha256": manifest["raw_snapshot"]["sha256"],
                "redistribution_status": manifest["source"]["redistribution_status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
