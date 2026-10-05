"""Command-line interface for the M6 point-in-time news/event pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .news_events import (
    NewsEventError,
    build_entity_catalog,
    build_intelligence_digest,
    create_event_snapshot,
    evaluate_event_predictions,
    label_forward_returns,
    normalize_news_documents,
    prepare_extraction_documents,
    query_event_snapshots_as_of,
    query_news_documents_as_of,
    watch_breaking_events,
)


def _read_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NewsEventError(f"cannot read JSON from {path}: {exc}") from exc


def _write_json(value: Any, path: str) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path == "-":
        sys.stdout.write(rendered)
        return
    try:
        Path(path).write_text(rendered, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise NewsEventError(f"cannot write JSON to {path}: {exc}") from exc


def _rows(value: Any, field: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and isinstance(value.get(field), list):
        rows = value[field]
    else:
        raise NewsEventError(f"input must be an array or an object with a {field!r} array")
    if any(not isinstance(row, dict) for row in rows):
        raise NewsEventError(f"{field} must contain only JSON objects")
    return rows


def _json_file_argument(parser: argparse.ArgumentParser, *flags: str, **kwargs: Any) -> None:
    parser.add_argument(*flags, type=str, **kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-news", description="M6 point-in-time news/event processing")
    commands = parser.add_subparsers(dest="command", required=True)

    normalize = commands.add_parser("normalize", help="validate and deduplicate raw article revisions")
    _json_file_argument(normalize, "--input", required=True, help="raw JSON array or {documents: [...]} file")
    normalize.add_argument("--output", default="-", help="output JSON path (default: stdout)")

    prepare = commands.add_parser("prepare-extraction", help="select point-in-time source text for extraction")
    _json_file_argument(prepare, "--input", required=True, help="normalized article JSON file")
    prepare.add_argument("--as-of", required=True, help="timezone-aware ISO-8601 source/system cutoff")
    prepare.add_argument("--mode", choices=("source", "system"), default="source")
    prepare.add_argument("--output", default="-")

    documents_as_of = commands.add_parser("documents-as-of", help="query source document revisions by cutoff")
    _json_file_argument(documents_as_of, "--input", required=True)
    documents_as_of.add_argument("--as-of", required=True)
    documents_as_of.add_argument("--mode", choices=("source", "system"), default="source")
    documents_as_of.add_argument("--output", default="-")

    snapshot = commands.add_parser("create-snapshot", help="bind a structured extraction to one article revision")
    _json_file_argument(snapshot, "--document", required=True, help="one normalized document JSON file")
    _json_file_argument(snapshot, "--extraction", required=True, help="structured extraction JSON file")
    _json_file_argument(snapshot, "--universe", required=True, help="M1 universe JSON file")
    snapshot.add_argument("--extraction-version", required=True)
    snapshot.add_argument("--model", required=True, help="model identifier recorded as provenance")
    snapshot.add_argument("--prompt-sha256", required=True)
    snapshot.add_argument("--completed-at", required=True)
    snapshot.add_argument("--ingestion-time", required=True)
    snapshot.add_argument("--output", default="-")

    events_as_of = commands.add_parser("events-as-of", help="query event snapshots by feature/system cutoff")
    _json_file_argument(events_as_of, "--input", required=True, help="snapshot array or {snapshots: [...]} file")
    events_as_of.add_argument("--as-of", required=True)
    events_as_of.add_argument("--mode", choices=("source", "system"), default="system")
    events_as_of.add_argument("--extraction-version")
    events_as_of.add_argument("--output", default="-")

    digest = commands.add_parser("digest", help="build an informational morning/overnight digest")
    _json_file_argument(digest, "--input", required=True)
    digest.add_argument("--window-start", required=True)
    digest.add_argument("--as-of", required=True)
    digest.add_argument("--timezone", required=True, help="IANA timezone name")
    digest.add_argument("--minimum-materiality", default="0")
    digest.add_argument("--mode", choices=("source", "system"), default="system")
    digest.add_argument("--extraction-version")
    digest.add_argument("--output", default="-")

    watch = commands.add_parser("watch", help="poll material events after a stable cursor")
    _json_file_argument(watch, "--input", required=True)
    watch.add_argument("--after-time", required=True)
    watch.add_argument("--after-event-id", help="event ID at the cursor time; omit to start after the full time")
    watch.add_argument("--as-of", required=True)
    watch.add_argument("--timezone", required=True, help="IANA timezone name")
    watch.add_argument("--minimum-materiality", default="0.5")
    watch.add_argument("--mode", choices=("source", "system"), default="system")
    watch.add_argument("--extraction-version")
    watch.add_argument("--output", default="-")

    label = commands.add_parser("label-forward-returns", help="attach post-feature M2 close-to-close outcomes")
    _json_file_argument(label, "--snapshots", required=True)
    _json_file_argument(label, "--prices", required=True, help="M2 record array or {records: [...]} file")
    label.add_argument("--horizon-sessions", type=int, required=True)
    label.add_argument("--label-as-of", required=True, help="timezone-aware cutoff for public/system price revisions")
    label.add_argument("--price-dataset-id", required=True, help="dataset_id from the M2 manifest")
    label.add_argument("--mode", choices=("source", "system"), default="system")
    label.add_argument("--output", default="-")

    evaluate = commands.add_parser("evaluate", help="score OOS probabilities with a train-only base-rate baseline")
    _json_file_argument(evaluate, "--input", required=True, help="evaluation case JSON file")
    evaluate.add_argument("--output", default="-")
    return parser


def run(args: argparse.Namespace) -> Any:
    if args.command == "normalize":
        raw = _rows(_read_json(args.input), "documents")
        documents, duplicate_count = normalize_news_documents(raw)
        return _write_json({"schema_version": 1, "documents": documents, "duplicate_count": duplicate_count}, args.output)
    if args.command == "prepare-extraction":
        documents = _rows(_read_json(args.input), "documents")
        return _write_json(prepare_extraction_documents(documents, args.as_of, mode=args.mode), args.output)
    if args.command == "documents-as-of":
        documents = _rows(_read_json(args.input), "documents")
        return _write_json(query_news_documents_as_of(documents, args.as_of, mode=args.mode), args.output)
    if args.command == "create-snapshot":
        document = _read_json(args.document)
        extraction = _read_json(args.extraction)
        universe = _read_json(args.universe)
        return _write_json(create_event_snapshot(
            document,
            extraction,
            entity_catalog=build_entity_catalog(universe),
            extraction_version=args.extraction_version,
            extraction_model=args.model,
            prompt_sha256=args.prompt_sha256,
            extraction_completed_at=args.completed_at,
            ingestion_time=args.ingestion_time,
        ), args.output)
    if args.command == "events-as-of":
        snapshots = _rows(_read_json(args.input), "snapshots")
        return _write_json(query_event_snapshots_as_of(
            snapshots, args.as_of, mode=args.mode, extraction_version=args.extraction_version
        ), args.output)
    if args.command == "digest":
        snapshots = _rows(_read_json(args.input), "snapshots")
        return _write_json(build_intelligence_digest(
            snapshots,
            window_start=args.window_start,
            as_of=args.as_of,
            timezone_name=args.timezone,
            minimum_materiality=args.minimum_materiality,
            mode=args.mode,
            extraction_version=args.extraction_version,
        ), args.output)
    if args.command == "watch":
        snapshots = _rows(_read_json(args.input), "snapshots")
        return _write_json(watch_breaking_events(
            snapshots,
            after_time=args.after_time,
            after_event_id=args.after_event_id,
            as_of=args.as_of,
            timezone_name=args.timezone,
            minimum_materiality=args.minimum_materiality,
            mode=args.mode,
            extraction_version=args.extraction_version,
        ), args.output)
    if args.command == "label-forward-returns":
        snapshots = _rows(_read_json(args.snapshots), "snapshots")
        prices = _rows(_read_json(args.prices), "records")
        return _write_json(label_forward_returns(
            snapshots,
            prices,
            horizon_sessions=args.horizon_sessions,
            label_as_of=args.label_as_of,
            price_dataset_id=args.price_dataset_id,
            mode=args.mode,
        ), args.output)
    if args.command == "evaluate":
        return _write_json(evaluate_event_predictions(_read_json(args.input)), args.output)
    raise NewsEventError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run(args)
    except (NewsEventError, OSError, TypeError, ValueError) as exc:
        print(f"actinver-news: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
