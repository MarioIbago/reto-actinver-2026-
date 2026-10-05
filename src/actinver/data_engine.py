"""Immutable, point-in-time data ingestion and query primitives.

The engine accepts a normalized JSONL/CSV contract. Vendor-specific adapters
must map into that contract without changing the original source file.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = 1
_REQUIRED_FIELDS = {
    "record_id",
    "instrument_id",
    "record_type",
    "event_time",
    "available_time",
    "source_revision",
    "payload",
}
_OPTIONAL_FIELDS = {"schema_version", "source_id", "ingestion_time", "provider_symbol"}
_CSV_COLUMNS = [
    "record_id",
    "instrument_id",
    "record_type",
    "event_time",
    "available_time",
    "ingestion_time",
    "source_revision",
    "provider_symbol",
    "payload_json",
]
_REDISTRIBUTION_STATUSES = {"permitted", "restricted", "unknown"}
_SOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_ADJUSTMENT_POLICY = "raw_unadjusted; corporate actions remain separate records"


class DataEngineError(ValueError):
    """Raised when a data record, source contract, or dataset is unsafe to use."""


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DataEngineError(f"{field} must be an ISO-8601 timestamp with timezone")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DataEngineError(f"{field} must be an ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataEngineError(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="auto").replace("+00:00", "Z")


def _json_safe(value: Any, path: str = "payload") -> Any:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise DataEngineError(f"{path} contains a non-finite decimal")
        return format(value, "f")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DataEngineError(f"{path} contains a non-finite number")
        raise DataEngineError(
            f"{path} contains a binary float; use a decimal string or integer for reproducibility"
        )
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(item, f"{path}[]") for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise DataEngineError(f"{path} object keys must be strings")
        return {key: _json_safe(item, f"{path}.{key}") for key, item in value.items()}
    raise DataEngineError(f"{path} contains unsupported value type {type(value).__name__}")


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise DataEngineError(f"{field} must be an exact decimal string or integer")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DataEngineError(f"{field} must be a valid decimal") from exc
    if not parsed.is_finite() or parsed < 0 or (positive and parsed == 0):
        qualifier = "positive" if positive else "non-negative"
        raise DataEngineError(f"{field} must be finite and {qualifier}")
    return parsed


def normalize_record(
    raw: Mapping[str, Any],
    *,
    default_source_id: str | None = None,
    default_ingestion_time: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise DataEngineError("Each record must be an object")
    if any(not isinstance(key, str) for key in raw):
        raise DataEngineError("Record field names must be strings")
    allowed = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
    extra = sorted(set(raw) - allowed)
    missing = sorted(_REQUIRED_FIELDS - set(raw))
    if extra:
        raise DataEngineError(f"Unknown record fields: {', '.join(extra)}")
    if missing:
        raise DataEngineError(f"Missing required record fields: {', '.join(missing)}")
    schema_version = raw.get("schema_version", SCHEMA_VERSION)
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        raise DataEngineError("Unsupported record schema_version")

    source_id = raw.get("source_id") or default_source_id
    if not isinstance(source_id, str) or not _SOURCE_ID_PATTERN.fullmatch(source_id):
        raise DataEngineError("source_id is required and must be a safe identifier")
    for field in ("record_id", "instrument_id", "record_type", "source_revision"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DataEngineError(f"{field} must be a non-empty string")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", raw["record_type"]):
        raise DataEngineError("record_type must be lower_snake_case")
    if not isinstance(raw["payload"], dict):
        raise DataEngineError("payload must be an object")

    event_time = _parse_time(raw["event_time"], "event_time")
    available_time = _parse_time(raw["available_time"], "available_time")
    ingestion_value = raw.get("ingestion_time") or default_ingestion_time
    ingestion_time = _parse_time(ingestion_value, "ingestion_time")
    if ingestion_time < available_time:
        raise DataEngineError("ingestion_time cannot precede source available_time")

    payload = _json_safe(raw["payload"])
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_id": raw["record_id"].strip(),
        "instrument_id": raw["instrument_id"].strip(),
        "record_type": raw["record_type"],
        "event_time": _format_time(event_time),
        "available_time": _format_time(available_time),
        "ingestion_time": _format_time(ingestion_time),
        "source_id": source_id,
        "source_revision": raw["source_revision"].strip(),
        "payload": payload,
    }
    provider_symbol = raw.get("provider_symbol")
    if provider_symbol is not None:
        if not isinstance(provider_symbol, str) or not provider_symbol.strip():
            raise DataEngineError("provider_symbol must be null or a non-empty string")
        record["provider_symbol"] = provider_symbol.strip()

    _validate_record_semantics(record)
    return record


def _validate_record_semantics(record: Mapping[str, Any]) -> None:
    record_type = record["record_type"]
    event_time = _parse_time(record["event_time"], "event_time")
    available_time = _parse_time(record["available_time"], "available_time")
    payload = record["payload"]

    if record_type == "price_bar":
        if available_time < event_time:
            raise DataEngineError("price_bar available_time cannot precede bar event_time")
        missing = sorted({"open", "high", "low", "close", "volume"} - set(payload))
        if missing:
            raise DataEngineError(f"price_bar payload is missing: {', '.join(missing)}")
        prices = {
            field: _decimal(payload[field], f"price_bar.{field}", positive=True)
            for field in ("open", "high", "low", "close")
        }
        volume = _decimal(payload["volume"], "price_bar.volume")
        if prices["high"] < max(prices["open"], prices["close"], prices["low"]):
            raise DataEngineError("price_bar.high must be at least open, close, and low")
        if prices["low"] > min(prices["open"], prices["close"]):
            raise DataEngineError("price_bar.low must not exceed open or close")
        if volume < 0:
            raise DataEngineError("price_bar.volume must be non-negative")
    elif record_type == "market_trade":
        if available_time < event_time:
            raise DataEngineError("market_trade available_time cannot precede trade event_time")
        _decimal(payload.get("price"), "market_trade.price", positive=True)
        _decimal(payload.get("quantity"), "market_trade.quantity")
    elif record_type == "corporate_action":
        if "effective_time" not in payload:
            raise DataEngineError("corporate_action payload requires effective_time")
        _parse_time(payload["effective_time"], "corporate_action.effective_time")


def normalize_records(
    rows: Iterable[Mapping[str, Any]],
    *,
    default_source_id: str | None = None,
    default_ingestion_time: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Normalize, conservatively deduplicate and deterministically order records."""
    versions: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    duplicate_count = 0
    for raw in rows:
        row = normalize_record(
            raw,
            default_source_id=default_source_id,
            default_ingestion_time=default_ingestion_time,
        )
        key = (
            row["source_id"],
            row["record_id"],
            row["source_revision"],
            row["available_time"],
        )
        existing = versions.get(key)
        if existing is None:
            versions[key] = row
            continue
        existing_content = {k: v for k, v in existing.items() if k != "ingestion_time"}
        new_content = {k: v for k, v in row.items() if k != "ingestion_time"}
        if existing_content != new_content:
            raise DataEngineError(
                "Conflicting values share source_id, record_id, source_revision and available_time"
            )
        if _parse_time(row["ingestion_time"], "ingestion_time") < _parse_time(
            existing["ingestion_time"], "ingestion_time"
        ):
            versions[key] = row
        duplicate_count += 1

    # A provider must timestamp distinct revisions distinctly; otherwise source-as-of
    # reconstruction cannot determine which value was publicly visible at the cutoff.
    by_publication: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in versions.values():
        publication_key = (row["source_id"], row["record_id"], row["available_time"])
        existing = by_publication.get(publication_key)
        existing_content = {
            key: value
            for key, value in existing.items()
            if key not in {"source_revision", "ingestion_time"}
        } if existing is not None else None
        current_content = {
            key: value
            for key, value in row.items()
            if key not in {"source_revision", "ingestion_time"}
        }
        if existing is not None and existing_content != current_content:
            raise DataEngineError(
                "Conflicting revisions have the same source available_time; "
                "preserve a finer timestamp"
            )
        by_publication[publication_key] = row

    normalized = sorted(
        versions.values(),
        key=lambda item: (
            item["instrument_id"],
            item["record_type"],
            _parse_time(item["event_time"], "event_time"),
            _parse_time(item["available_time"], "available_time"),
            item["source_id"],
            item["record_id"],
            item["source_revision"],
        ),
    )
    return normalized, duplicate_count


def query_as_of(
    records: Iterable[Mapping[str, Any]],
    as_of: str,
    *,
    mode: str = "source",
) -> list[dict[str, Any]]:
    """Return the latest revisions knowable by a timestamp.

    `source` reconstructs what the source had published. `system` additionally
    requires the record to have been ingested by this project by that time.
    Known future calendar/news events are retained; future price bars are excluded.
    """
    if mode not in {"source", "system"}:
        raise DataEngineError("mode must be 'source' or 'system'")
    cutoff = _parse_time(as_of, "as_of")
    normalized_records, _duplicates = normalize_records(records)
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for item in normalized_records:
        row = normalize_record(item)
        available = _parse_time(row["available_time"], "available_time")
        ingested = _parse_time(row["ingestion_time"], "ingestion_time")
        event = _parse_time(row["event_time"], "event_time")
        if available > cutoff:
            continue
        if mode == "system" and ingested > cutoff:
            continue
        if row["record_type"] == "price_bar" and event > cutoff:
            continue
        key = (row["source_id"], row["record_id"])
        previous = latest.get(key)
        if previous is None or available > _parse_time(previous["available_time"], "available_time"):
            latest[key] = row
        elif (
            available == _parse_time(previous["available_time"], "available_time")
            and row["payload"] != previous["payload"]
        ):
            raise DataEngineError("Ambiguous same-time source revisions in point-in-time query")
    return sorted(
        latest.values(),
        key=lambda item: (
            _parse_time(item["event_time"], "event_time"),
            item["instrument_id"],
            item["record_type"],
            item["source_id"],
            item["record_id"],
        ),
    )


def require_fresh_price_bars(
    records: Iterable[Mapping[str, Any]],
    as_of: str,
    *,
    max_age_seconds: int,
    mode: str = "source",
    expected_instrument_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Fail closed if the supplied point-in-time view has missing or stale prices.

    Call this on the output of `query_as_of`, with the expected freshness threshold
    chosen from a versioned market-data policy. The newest bar is checked per
    instrument, and callers can fail closed on missing expected instruments by
    supplying `expected_instrument_ids`.
    """
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise DataEngineError("max_age_seconds must be a non-negative integer")
    if mode not in {"source", "system"}:
        raise DataEngineError("mode must be 'source' or 'system'")
    expected: set[str] | None = None
    if expected_instrument_ids is not None:
        if isinstance(expected_instrument_ids, (str, bytes)):
            raise DataEngineError("expected_instrument_ids must be an iterable of identifiers")
        expected_values = list(expected_instrument_ids)
        if not expected_values or any(
            not isinstance(value, str) or not value.strip() for value in expected_values
        ):
            raise DataEngineError("expected_instrument_ids must contain non-empty identifiers")
        if len(set(expected_values)) != len(expected_values):
            raise DataEngineError("expected_instrument_ids must not contain duplicates")
        expected = set(expected_values)
    cutoff = _parse_time(as_of, "as_of")
    normalized_records, _duplicates = normalize_records(records)
    price_bars = [row for row in normalized_records if row["record_type"] == "price_bar"]
    if not price_bars:
        raise DataEngineError("No price_bar records are available for freshness validation")

    latest_by_instrument: dict[str, dict[str, Any]] = {}
    for row in price_bars:
        available_time = _parse_time(row["available_time"], "available_time")
        ingestion_time = _parse_time(row["ingestion_time"], "ingestion_time")
        event_time = _parse_time(row["event_time"], "event_time")
        if available_time > cutoff:
            raise DataEngineError(
                "Unpublished price_bar is present for "
                f"{row['instrument_id']} at {row['available_time']}"
            )
        if mode == "system" and ingestion_time > cutoff:
            raise DataEngineError(
                "Not-yet-ingested price_bar is present for "
                f"{row['instrument_id']} at {row['ingestion_time']}"
            )
        if event_time > cutoff:
            raise DataEngineError(
                "Future price_bar event is present for "
                f"{row['instrument_id']} at {row['event_time']}"
            )
        previous = latest_by_instrument.get(row["instrument_id"])
        if previous is None or event_time > _parse_time(previous["event_time"], "event_time"):
            latest_by_instrument[row["instrument_id"]] = row

    if expected is not None:
        missing = sorted(expected - set(latest_by_instrument))
        if missing:
            raise DataEngineError(
                "Missing price_bar coverage for expected instruments: " + ", ".join(missing)
            )

    stale: list[dict[str, Any]] = []
    for row in latest_by_instrument.values():
        event_time = _parse_time(row["event_time"], "event_time")
        age = cutoff - event_time
        age_seconds = int(age.total_seconds())
        if age > timedelta(seconds=max_age_seconds):
            stale.append(
                {
                    "instrument_id": row["instrument_id"],
                    "record_id": row["record_id"],
                    "event_time": row["event_time"],
                    "age_seconds": age_seconds,
                }
            )
    if stale:
        identifiers = ", ".join(
            f"{item['instrument_id']} ({item['age_seconds']}s; {item['event_time']})"
            for item in sorted(stale, key=lambda item: item["instrument_id"])
        )
        raise DataEngineError(
            f"Stale price_bar records exceed {max_age_seconds}s for: {identifiers}"
        )
    return {
        "status": "PASS",
        "checked_instruments": len(latest_by_instrument),
        "historical_price_bars_considered": len(price_bars),
        "coverage_status": "CHECKED" if expected is not None else "NOT_CHECKED",
        "expected_instrument_count": len(expected) if expected is not None else None,
        "availability_mode": mode,
        "max_age_seconds": max_age_seconds,
        "as_of": _format_time(cutoff),
        "stale": [],
    }


def _canonical_json(value: Any) -> bytes:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (encoded + "\n").encode("utf-8")


def _jsonl_bytes(records: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json(dict(record)) for record in records)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_url(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DataEngineError(f"{field} must be an http(s) URL")
    if not value.strip():
        return None
    try:
        parts = urlsplit(value.strip())
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise DataEngineError(f"{field} must be a valid http(s) URL") from exc
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or not hostname
        or (port is not None and not 1 <= port <= 65535)
        or any(character.isspace() for character in hostname)
    ):
        raise DataEngineError(f"{field} must be an http(s) URL")
    if parts.username or parts.password:
        raise DataEngineError(f"{field} must not contain credentials")
    if parts.query:
        raise DataEngineError(
            f"{field} must not contain query parameters; provide a canonical public URL"
        )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _dataset_id(
    source: Mapping[str, Any],
    raw_sha256: str,
    records: list[dict[str, Any]],
    built_at_utc: str,
    code_commit_sha: str,
) -> str:
    source_content = {
        "schema_version": SCHEMA_VERSION,
        "source": dict(source),
        "raw_sha256": raw_sha256,
        "records": records,
        "built_at_utc": built_at_utc,
        "code_commit_sha": code_commit_sha,
        "adjustment_policy": _ADJUSTMENT_POLICY,
    }
    return f"actinver-pit-v{SCHEMA_VERSION}-{_sha256(_canonical_json(source_content))}"


def _write_immutable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise DataEngineError(f"Refusing to overwrite immutable artifact: {path}")
        return
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise DataEngineError(f"Immutable artifact was concurrently replaced: {path}")


def _decode_json(text: str, line_number: int) -> Any:
    if not isinstance(text, str):
        raise DataEngineError(f"Invalid JSON on line {line_number}: value must be text")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DataEngineError(
                    f"Duplicate JSON object key {key!r} on line {line_number}"
                )
            result[key] = value
        return result

    try:
        return json.loads(text, parse_float=Decimal, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise DataEngineError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc


def _read_source_rows(content: bytes, suffix: str) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataEngineError("Input must be UTF-8 encoded") from exc
    if suffix.lower() in {".jsonl", ".ndjson"}:
        rows = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.strip():
                value = _decode_json(line, line_number)
                if not isinstance(value, dict):
                    raise DataEngineError(f"JSONL line {line_number} must contain an object")
                rows.append(value)
        return rows
    if suffix.lower() == ".csv":
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None or reader.fieldnames != _CSV_COLUMNS:
            raise DataEngineError(
                "CSV headers must match the normalized contract in this order: "
                + ",".join(_CSV_COLUMNS)
            )
        rows = []
        for line_number, csv_row in enumerate(reader, 2):
            if None in csv_row:
                raise DataEngineError(f"CSV line {line_number} has extra columns")
            missing_cells = sorted(key for key, value in csv_row.items() if value is None)
            if missing_cells:
                raise DataEngineError(
                    f"CSV line {line_number} has missing cells: {', '.join(missing_cells)}"
                )
            raw = dict(csv_row)
            payload_text = raw.pop("payload_json")
            parsed_payload = _decode_json(payload_text, line_number)
            raw["payload"] = parsed_payload
            for key in ("source_id",):
                raw.pop(key, None)
            for key in ("ingestion_time", "provider_symbol"):
                if raw.get(key) == "":
                    raw[key] = None
            rows.append(raw)
        return rows
    raise DataEngineError("Input file extension must be .jsonl, .ndjson or .csv")


def build_dataset(
    input_path: str | Path,
    project_root: str | Path,
    *,
    source_id: str,
    publisher: str,
    license_id: str,
    redistribution_status: str,
    ingestion_time: str,
    code_commit_sha: str,
    source_url: str | None = None,
    license_url: str | None = None,
) -> dict[str, Any]:
    """Archive raw bytes and create immutable interim/processed snapshots + manifest."""
    if not isinstance(source_id, str) or not _SOURCE_ID_PATTERN.fullmatch(source_id):
        raise DataEngineError("source_id must be a safe identifier")
    if (
        not isinstance(publisher, str)
        or not publisher.strip()
        or not isinstance(license_id, str)
        or not license_id.strip()
    ):
        raise DataEngineError("publisher and license_id are required")
    if redistribution_status not in _REDISTRIBUTION_STATUSES:
        raise DataEngineError(
            "redistribution_status must be permitted, restricted or unknown"
        )
    if not isinstance(code_commit_sha, str) or not re.fullmatch(
        r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", code_commit_sha.strip()
    ):
        raise DataEngineError("code_commit_sha must be a full 40- or 64-character Git SHA")
    if not isinstance(ingestion_time, str):
        raise DataEngineError("ingestion_time must be supplied explicitly for reproducibility")
    normalized_ingestion_time = _format_time(_parse_time(ingestion_time, "ingestion_time"))
    safe_source_url = _source_url(source_url, "source_url")
    safe_license_url = _source_url(license_url, "license_url")

    source_path = Path(input_path)
    raw_bytes = source_path.read_bytes()
    raw_sha = _sha256(raw_bytes)
    suffix = source_path.suffix.lower()
    if suffix not in {".jsonl", ".ndjson", ".csv"}:
        raise DataEngineError("Input file extension must be .jsonl, .ndjson or .csv")
    root = Path(project_root).resolve()
    raw_relative = Path("data") / "raw" / source_id / f"{raw_sha}{suffix}"
    raw_path = _safe_manifest_path(root, raw_relative.as_posix())
    _write_immutable(raw_path, raw_bytes)

    raw_rows = _read_source_rows(raw_bytes, suffix)
    normalized, duplicate_count = normalize_records(
        raw_rows,
        default_source_id=source_id,
        default_ingestion_time=normalized_ingestion_time,
    )
    if not normalized:
        raise DataEngineError("Input dataset contains no records")
    if any(row["source_id"] != source_id for row in normalized):
        raise DataEngineError("All rows in one input file must use the declared source_id")

    source = {
        "source_id": source_id,
        "publisher": publisher.strip(),
        "source_url": safe_source_url,
        "license_id": license_id.strip(),
        "license_url": safe_license_url,
        "redistribution_status": redistribution_status,
    }
    dataset_id = _dataset_id(
        source,
        raw_sha,
        normalized,
        normalized_ingestion_time,
        code_commit_sha.strip(),
    )

    interim_records = sorted(
        normalized,
        key=lambda item: (
            item["source_id"],
            item["record_id"],
            item["available_time"],
            item["source_revision"],
        ),
    )
    processed_records = sorted(
        normalized,
        key=lambda item: (
            item["instrument_id"],
            item["record_type"],
            item["event_time"],
            item["available_time"],
            item["source_id"],
            item["record_id"],
        ),
    )
    interim_bytes = _jsonl_bytes(interim_records)
    processed_bytes = _jsonl_bytes(processed_records)
    interim_relative = Path("data") / "interim" / f"{dataset_id}.jsonl"
    processed_relative = Path("data") / "processed" / f"{dataset_id}.jsonl"
    interim_path = _safe_manifest_path(root, interim_relative.as_posix())
    processed_path = _safe_manifest_path(root, processed_relative.as_posix())
    _write_immutable(interim_path, interim_bytes)
    _write_immutable(processed_path, processed_bytes)

    event_times = [row["event_time"] for row in normalized]
    available_times = [row["available_time"] for row in normalized]
    type_counts: dict[str, int] = {}
    for row in normalized:
        type_counts[row["record_type"]] = type_counts.get(row["record_type"], 0) + 1
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "record_schema_version": SCHEMA_VERSION,
        "source": source,
        "raw_snapshot": {
            "path": raw_relative.as_posix(),
            "sha256": raw_sha,
            "size_bytes": len(raw_bytes),
        },
        "interim_snapshot": {
            "path": interim_relative.as_posix(),
            "sha256": _sha256(interim_bytes),
        },
        "processed_snapshot": {
            "path": processed_relative.as_posix(),
            "sha256": _sha256(processed_bytes),
        },
        "records": {
            "input_count": len(raw_rows),
            "unique_version_count": len(normalized),
            "duplicates_removed": duplicate_count,
            "counts_by_type": dict(sorted(type_counts.items())),
            "event_time_range": {"start": min(event_times), "end": max(event_times)},
            "available_time_range": {
                "start": min(available_times),
                "end": max(available_times),
            },
        },
        "build": {
            "built_at_utc": normalized_ingestion_time,
            "code_commit_sha": code_commit_sha.strip(),
            "adjustment_policy": _ADJUSTMENT_POLICY,
        },
    }
    manifest_relative = Path("data") / "metadata" / "datasets" / f"{dataset_id}.json"
    manifest_bytes = _canonical_json(manifest)
    manifest_output_path = _safe_manifest_path(root, manifest_relative.as_posix())
    _write_immutable(manifest_output_path, manifest_bytes)
    return manifest


def _safe_manifest_path(root: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise DataEngineError("Manifest snapshot path must be a non-empty string")
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise DataEngineError("Manifest paths must remain inside the project root") from exc
    return candidate


def verify_manifest(manifest_path: str | Path, project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8")
        manifest = _decode_json(manifest_text, 1)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataEngineError(f"Could not read dataset manifest: {exc}") from exc
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("schema_version")) is not int
        or manifest.get("schema_version") != SCHEMA_VERSION
        or type(manifest.get("record_schema_version")) is not int
        or manifest.get("record_schema_version") != SCHEMA_VERSION
    ):
        raise DataEngineError("Unsupported or malformed dataset manifest")
    for section in ("raw_snapshot", "interim_snapshot", "processed_snapshot"):
        snapshot = manifest.get(section)
        if (
            not isinstance(snapshot, dict)
            or not isinstance(snapshot.get("path"), str)
            or not snapshot.get("path")
            or not isinstance(snapshot.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", snapshot["sha256"])
        ):
            raise DataEngineError(f"Manifest is missing {section} path/hash")
        path = _safe_manifest_path(root, snapshot["path"])
        try:
            observed = _file_sha256(path)
        except OSError as exc:
            raise DataEngineError(f"Missing or unreadable snapshot {snapshot['path']}") from exc
        if observed != snapshot["sha256"]:
            raise DataEngineError(f"SHA-256 mismatch for {snapshot['path']}")
    raw_snapshot = manifest["raw_snapshot"]
    raw_path = _safe_manifest_path(root, raw_snapshot["path"])
    raw_bytes = raw_path.read_bytes()
    if (
        type(raw_snapshot.get("size_bytes")) is not int
        or len(raw_bytes) != raw_snapshot["size_bytes"]
    ):
        raise DataEngineError("Raw snapshot size does not match the manifest")
    raw_suffix = raw_path.suffix.lower()
    raw_rows = _read_source_rows(raw_bytes, raw_suffix)

    source = manifest.get("source")
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("source_id"), str)
        or not _SOURCE_ID_PATTERN.fullmatch(source["source_id"])
        or not isinstance(source.get("publisher"), str)
        or not source["publisher"].strip()
        or not isinstance(source.get("license_id"), str)
        or not source["license_id"].strip()
        or source.get("redistribution_status") not in _REDISTRIBUTION_STATUSES
    ):
        raise DataEngineError("Manifest source metadata is malformed")
    source = {
        "source_id": source["source_id"],
        "publisher": source["publisher"].strip(),
        "source_url": _source_url(source.get("source_url"), "source_url"),
        "license_id": source["license_id"].strip(),
        "license_url": _source_url(source.get("license_url"), "license_url"),
        "redistribution_status": source["redistribution_status"],
    }
    build = manifest.get("build")
    if (
        not isinstance(build, dict)
        or not isinstance(build.get("built_at_utc"), str)
        or not isinstance(build.get("code_commit_sha"), str)
        or not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", build["code_commit_sha"])
        or build.get("adjustment_policy") != _ADJUSTMENT_POLICY
    ):
        raise DataEngineError("Manifest build metadata is malformed")
    built_at_utc = _format_time(_parse_time(build["built_at_utc"], "built_at_utc"))
    code_commit_sha = build["code_commit_sha"]

    normalized_raw, raw_duplicates = normalize_records(
        raw_rows,
        default_source_id=source["source_id"],
        default_ingestion_time=built_at_utc,
    )
    if not normalized_raw or any(row["source_id"] != source["source_id"] for row in normalized_raw):
        raise DataEngineError("Raw snapshot source_id does not match the manifest")
    interim_path = _safe_manifest_path(root, manifest["interim_snapshot"]["path"])
    interim_rows = _read_source_rows(interim_path.read_bytes(), ".jsonl")
    normalized_interim, interim_duplicates = normalize_records(interim_rows)

    processed_path = _safe_manifest_path(root, manifest["processed_snapshot"]["path"])
    processed_rows = _read_source_rows(processed_path.read_bytes(), ".jsonl")
    normalized_processed, processed_duplicates = normalize_records(processed_rows)
    if (
        interim_duplicates != 0
        or processed_duplicates != 0
        or normalized_raw != normalized_interim
        or normalized_raw != normalized_processed
    ):
        raise DataEngineError("Raw, interim, and processed records do not agree")

    expected_dataset_id = _dataset_id(
        source,
        raw_snapshot["sha256"],
        normalized_raw,
        built_at_utc,
        code_commit_sha,
    )
    if manifest.get("dataset_id") != expected_dataset_id:
        raise DataEngineError("Dataset ID does not match source, records, and build provenance")

    type_counts: dict[str, int] = {}
    for row in normalized_raw:
        type_counts[row["record_type"]] = type_counts.get(row["record_type"], 0) + 1
    event_times = [row["event_time"] for row in normalized_raw]
    available_times = [row["available_time"] for row in normalized_raw]
    record_summary = manifest.get("records")
    if (
        not isinstance(record_summary, dict)
        or type(record_summary.get("unique_version_count")) is not int
        or type(record_summary.get("input_count")) is not int
        or type(record_summary.get("duplicates_removed")) is not int
        or record_summary["input_count"] != len(raw_rows)
        or record_summary["duplicates_removed"] != raw_duplicates
        or record_summary["unique_version_count"] != len(normalized_raw)
        or record_summary.get("counts_by_type") != dict(sorted(type_counts.items()))
        or record_summary.get("event_time_range")
        != {"start": min(event_times), "end": max(event_times)}
        or record_summary.get("available_time_range")
        != {"start": min(available_times), "end": max(available_times)}
    ):
        raise DataEngineError("Record summary does not match raw/interim/processed data")
    return {
        "status": "PASS",
        "dataset_id": manifest["dataset_id"],
        "records": len(normalized_raw),
        "source_id": source["source_id"],
        "source_fingerprints": "PASS",
    }


def read_dataset(
    manifest_path: str | Path,
    project_root: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = Path(project_root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file
    verify_manifest(manifest_file, root)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    processed_path = _safe_manifest_path(root, manifest["processed_snapshot"]["path"])
    rows = _read_source_rows(processed_path.read_bytes(), ".jsonl")
    normalized, _duplicates = normalize_records(rows)
    return manifest, normalized
