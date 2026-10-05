"""M9 human-readable reports, tamper-evident audit records, and attribution.

The current M7 and M8 empirical gates are not passed. Reports therefore fail
closed to NO_TRADE; this module never places or transmits orders.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterator, Mapping
from uuid import uuid4

from .news_events import NewsEventError, flatten_event_snapshots, query_event_snapshots_as_of, validate_event_snapshot


class TradeSheetError(ValueError):
    """Raised when an M9 input, report, or audit record is invalid."""


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPORT_TYPES = {"morning", "event_update", "evening_review"}
AUDIT_EVENT_TYPES = {"TRADE_SHEET_CREATED", "POST_TRADE_ATTRIBUTION_CREATED"}


def _canonical(value: Any) -> bytes:
    try:
        rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return rendered.encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TradeSheetError(f"value cannot be encoded as finite canonical JSON: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _object(value: Any, required: set[str], optional: set[str], name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise TradeSheetError(f"{name} must be an object")
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise TradeSheetError(f"{name} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise TradeSheetError(f"{name} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise TradeSheetError(f"{name} must be a non-empty string")
    return value.strip()


def _number(value: Any, name: str, *, nullable: bool = False, minimum: float | None = None) -> float | None:
    if nullable and value is None:
        return None
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise TradeSheetError(f"{name} must be a finite number" + (" or null" if nullable else ""))
    number = float(value)
    if minimum is not None and number < minimum:
        raise TradeSheetError(f"{name} must be at least {minimum}")
    return number


def _integer(value: Any, name: str, *, nullable: bool = False, minimum: int = 0) -> int | None:
    if nullable and value is None:
        return None
    if type(value) is not int or value < minimum:
        raise TradeSheetError(f"{name} must be an integer at least {minimum}" + (" or null" if nullable else ""))
    return value


def _instant(value: Any, name: str, *, nullable: bool = False) -> datetime | None:
    if nullable and value is None:
        return None
    if type(value) is not str:
        raise TradeSheetError(f"{name} must be an ISO-8601 timestamp with an offset" + (" or null" if nullable else ""))
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise TradeSheetError(f"{name} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TradeSheetError(f"{name} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _utc(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    precision = "microseconds" if normalized.microsecond else "seconds"
    return normalized.isoformat(timespec=precision).replace("+00:00", "Z")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = item
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value}")


def read_json(path: Path) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        return value, raw
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise TradeSheetError(f"cannot read JSON from {path}: {exc}") from exc


def _validate_context(value: Any) -> dict[str, Any]:
    context = _object(value, {"schema_version", "context_id", "as_of_utc", "competition", "portfolio", "data_sources"}, set(), "context")
    if type(context["schema_version"]) is not int or context["schema_version"] != 1:
        raise TradeSheetError("context.schema_version must equal 1")
    _text(context["context_id"], "context.context_id")
    as_of = _instant(context["as_of_utc"], "context.as_of_utc", nullable=True)

    competition = _object(context["competition"], {"capital_actipesos", "rank", "gap_to_first_actipesos", "sessions_remaining"}, set(), "context.competition")
    _number(competition["capital_actipesos"], "competition.capital_actipesos", nullable=True, minimum=0)
    _integer(competition["rank"], "competition.rank", nullable=True, minimum=1)
    _number(competition["gap_to_first_actipesos"], "competition.gap_to_first_actipesos", nullable=True)
    _integer(competition["sessions_remaining"], "competition.sessions_remaining", nullable=True, minimum=0)

    portfolio = _object(context["portfolio"], {"positions"}, set(), "context.portfolio")
    if portfolio["positions"] is not None:
        if type(portfolio["positions"]) is not list:
            raise TradeSheetError("portfolio.positions must be an array or null")
        seen_positions: set[str] = set()
        for index, raw_position in enumerate(portfolio["positions"]):
            position = _object(raw_position, {"instrument_id", "market_value_actipesos"}, set(), f"portfolio.positions[{index}]")
            instrument_id = _text(position["instrument_id"], f"portfolio.positions[{index}].instrument_id")
            if instrument_id in seen_positions:
                raise TradeSheetError(f"portfolio.positions contains duplicate instrument {instrument_id!r}")
            seen_positions.add(instrument_id)
            _number(position["market_value_actipesos"], f"portfolio.positions[{index}].market_value_actipesos", minimum=0)

    if type(context["data_sources"]) is not list:
        raise TradeSheetError("context.data_sources must be an array")
    seen_sources: set[str] = set()
    for index, raw_source in enumerate(context["data_sources"]):
        source = _object(raw_source, {"source_id", "observed_at_utc", "max_age_minutes"}, set(), f"context.data_sources[{index}]")
        source_id = _text(source["source_id"], f"context.data_sources[{index}].source_id")
        if source_id in seen_sources:
            raise TradeSheetError(f"context.data_sources contains duplicate source {source_id!r}")
        seen_sources.add(source_id)
        observed = _instant(source["observed_at_utc"], f"context.data_sources[{index}].observed_at_utc", nullable=True)
        max_age = _integer(source["max_age_minutes"], f"context.data_sources[{index}].max_age_minutes", nullable=True, minimum=1)
        if as_of is not None and observed is not None and observed > as_of:
            raise TradeSheetError(f"{source_id} was observed after the report as-of time")
        if max_age is None and source["max_age_minutes"] is not None:
            raise TradeSheetError(f"context.data_sources[{index}].max_age_minutes must be a positive integer or null")
    if as_of is not None and _utc(as_of) != context["as_of_utc"]:
        # All downstream comparisons use normalized instants; retain the user's original timestamp in provenance.
        pass
    return context


def _freshness(source: Mapping[str, Any], as_of: datetime | None) -> dict[str, Any]:
    observed = _instant(source["observed_at_utc"], f"{source['source_id']}.observed_at_utc", nullable=True)
    max_age = source["max_age_minutes"]
    if observed is None or max_age is None or as_of is None:
        status = "UNKNOWN"
        age = None
    else:
        seconds = (as_of - observed).total_seconds()
        age = max(0, math.ceil(seconds / 60))
        status = "CURRENT" if seconds <= max_age * 60 else "STALE"
    return {
        "source_id": source["source_id"],
        "observed_at_utc": source["observed_at_utc"],
        "max_age_minutes": max_age,
        "age_minutes_at_as_of": age,
        "status": status,
    }


def _m7_status(m7_result: Any | None) -> tuple[str, str]:
    if m7_result is None:
        return "NOT_SUPPLIED", "No se adjuntó un resultado M7."
    if type(m7_result) is not dict:
        raise TradeSheetError("M7 result must be a JSON object")
    status = str(m7_result.get("forecast_status", "UNKNOWN"))
    gate = str(m7_result.get("empirical_gate", "UNKNOWN"))
    if m7_result.get("software_status") != "PASS":
        return "INVALID_SOFTWARE_STATUS", "El resultado M7 no marca software_status=PASS."
    if status == "NO_PROMOTED_SIGNALS" or m7_result.get("signal_count") == 0:
        return "NO_PROMOTED_SIGNALS", "M7 no tiene señales financieras promovidas."
    if gate != "PASS":
        return gate, "M7 no ha superado su gate empírico; no se habilita ninguna instrucción."
    if status not in {"CALIBRATED", "CALIBRATED_OOS_MODEL"}:
        return status, "M7 no aporta un forecast calibrado para la decisión."
    if not m7_result.get("predictions"):
        return "NO_FORECAST", "El artefacto M7 no contiene forecasts."
    return "PASS", "M7 presenta un forecast calibrado y gate empírico PASS."


def _m8_status(m8_result: Any | None, m7_sha: str | None) -> tuple[str, str]:
    if m8_result is None:
        return "NOT_SUPPLIED", "No se adjuntó un resultado M8."
    if type(m8_result) is not dict:
        raise TradeSheetError("M8 result must be a JSON object")
    if m8_result.get("software_status") != "PASS":
        return "INVALID_SOFTWARE_STATUS", "El resultado M8 no marca software_status=PASS."
    trace = m8_result.get("input_trace")
    if type(trace) is not dict:
        return "INVALID_INPUT_TRACE", "M8 no incluye una traza verificable de entradas."
    bound_m7_sha = trace.get("m7_result_sha256")
    if bound_m7_sha is not None and (m7_sha is None or bound_m7_sha != m7_sha):
        return "M7_HASH_MISMATCH", "El SHA-256 M7 no coincide con el artefacto enlazado por M8."
    if m8_result.get("decision_status") == "SIMULATION_ONLY":
        return "SIMULATION_ONLY", "M8 solo presenta simulaciones; no ha emitido una decisión financiera."
    if m8_result.get("decision_status") == "NO_DECISION":
        return "NO_DECISION", "M8 no produjo una decisión utilizable."
    if m8_result.get("empirical_gate") != "PASS":
        return str(m8_result.get("empirical_gate", "UNKNOWN")), "M8 no ha superado su gate empírico."
    if m8_result.get("decision") is None:
        return "NO_DECISION", "M8 no produjo una decisión utilizable."
    return "PASS", "M8 presenta una decisión con gate empírico PASS."


def _events(snapshots: list[Any], as_of: datetime | None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if type(snapshots) is not list:
        raise TradeSheetError("event snapshots must be an array")
    if snapshots and as_of is None:
        raise TradeSheetError("context.as_of_utc is required when event snapshots are supplied")
    checked = []
    digests = []
    for index, raw in enumerate(snapshots):
        try:
            snapshot = validate_event_snapshot(raw, f"event_snapshots[{index}]")
        except NewsEventError as exc:
            raise TradeSheetError(str(exc)) from exc
        available = _instant(snapshot["feature_available_time"], f"event_snapshots[{index}].feature_available_time")
        ingested = _instant(snapshot["ingestion_time"], f"event_snapshots[{index}].ingestion_time")
        if as_of is not None and ((available is not None and available > as_of) or (ingested is not None and ingested > as_of)):
            raise TradeSheetError(f"event snapshot {snapshot['snapshot_id']} was unavailable at the report cutoff")
        checked.append(snapshot)
        digests.append({"snapshot_id": snapshot["snapshot_id"], "sha256": canonical_sha256(snapshot)})
    try:
        selected = query_event_snapshots_as_of(checked, _utc(as_of), mode="system") if as_of is not None else []
        flattened = flatten_event_snapshots(selected)
    except NewsEventError as exc:
        raise TradeSheetError(str(exc)) from exc
    unique: dict[str, dict[str, Any]] = {}
    comparable = {"event_type", "event_time", "entities", "novelty", "direction", "surprise_magnitude", "guidance_direction", "materiality", "confidence", "affected_sectors", "links"}
    for event in flattened:
        group = event["event_group_id"]
        previous = unique.get(group)
        if previous is None:
            unique[group] = event
            continue
        if any(previous.get(field) != event.get(field) for field in comparable):
            raise TradeSheetError("duplicate event content produced conflicting extraction values")
        if event["feature_available_time"] < previous["feature_available_time"]:
            unique[group] = event
    flattened = sorted(unique.values(), key=lambda event: (event["feature_available_time"], event["event_id"]))
    # Only preserve event facts and lineage needed by the operator view.
    rendered = []
    for event in flattened:
        rendered.append({
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "event_time": event["event_time"],
            "available_at_utc": event["feature_available_time"],
            "source_id": event["source_id"],
            "publisher": event["publisher"],
            "source_url": event["source_url"],
            "source_quality": event["source_quality"],
            "redistribution_status": event["redistribution_status"],
            "materiality": event["materiality"],
            "confidence": event["confidence"],
            "direction": event["direction"],
            "guidance_direction": event["guidance_direction"],
            "entities": deepcopy(event["entities"]),
            "affected_sectors": list(event["affected_sectors"]),
            "snapshot_id": event["snapshot_id"],
        })
    return rendered, digests


def build_trade_sheet(
    context: Any,
    *,
    report_type: str,
    m7_result: Any | None = None,
    m7_sha256: str | None = None,
    m8_result: Any | None = None,
    m8_sha256: str | None = None,
    event_snapshots: list[Any] | None = None,
    context_sha256: str | None = None,
    event_snapshot_sha256: list[str] | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a versioned report; the current M7/M8 gates always resolve to NO_TRADE."""
    if report_type not in REPORT_TYPES:
        raise TradeSheetError(f"report_type must be one of {', '.join(sorted(REPORT_TYPES))}")
    clean = _validate_context(context)
    created = created_at or datetime.now(timezone.utc)
    if created.tzinfo is None or created.utcoffset() is None:
        raise TradeSheetError("created_at must include a UTC offset")
    created = created.astimezone(timezone.utc)
    as_of = _instant(clean["as_of_utc"], "context.as_of_utc", nullable=True)
    if as_of is not None and as_of > created:
        raise TradeSheetError("context.as_of_utc cannot be later than report creation")
    m7_status, m7_reason = _m7_status(m7_result)
    m8_status, m8_reason = _m8_status(m8_result, m7_sha256)
    if m7_sha256 is not None and not SHA256_RE.fullmatch(m7_sha256):
        raise TradeSheetError("m7_sha256 must be a lowercase SHA-256 digest")
    if m8_sha256 is not None and not SHA256_RE.fullmatch(m8_sha256):
        raise TradeSheetError("m8_sha256 must be a lowercase SHA-256 digest")
    if context_sha256 is not None and not SHA256_RE.fullmatch(context_sha256):
        raise TradeSheetError("context_sha256 must be a lowercase SHA-256 digest")
    freshness = [_freshness(source, as_of) for source in clean["data_sources"]]
    event_rows, event_sources = _events(event_snapshots or [], as_of)
    if event_snapshot_sha256 is not None:
        if len(event_snapshot_sha256) != len(event_sources) or any(not SHA256_RE.fullmatch(item) for item in event_snapshot_sha256):
            raise TradeSheetError("event snapshot file digests must be SHA-256 values aligned with snapshots")
        for source, exact_digest in zip(event_sources, event_snapshot_sha256, strict=True):
            source["file_sha256"] = exact_digest
    for source in event_sources:
        source.setdefault("file_sha256", source["sha256"])

    reasons = [m7_reason, m8_reason]
    reasons.extend(f"La fuente {item['source_id']} está stale." for item in freshness if item["status"] == "STALE")
    reasons.extend(f"La frescura de {item['source_id']} es desconocida." for item in freshness if item["status"] == "UNKNOWN")
    if clean["as_of_utc"] is None:
        reasons.append("No se suministró una fecha de corte para los datos.")
    if clean["competition"]["capital_actipesos"] is None:
        reasons.append("No se suministró capital actual.")
    if clean["competition"]["rank"] is None or clean["competition"]["gap_to_first_actipesos"] is None:
        reasons.append("La posición o brecha del concurso no está disponible.")
    if clean["competition"]["sessions_remaining"] is None:
        reasons.append("No se suministraron las sesiones restantes.")
    if clean["portfolio"]["positions"] is None:
        reasons.append("Las posiciones actuales no fueron suministradas.")
    reasons.append("El mapeo autenticado de símbolos de M1 no está disponible.")
    reasons.append("La ejecución de órdenes en Actinver es manual y no forma parte de este sistema.")

    # M6 events inform the evidence timeline only. They never override the M7/M8 trade gate.
    if event_rows and not any(item["source_quality"] in {"primary_official", "primary_issuer"} for item in event_rows):
        reasons.append("Los eventos suministrados no incluyen una fuente primaria confirmada.")

    if m7_status != "PASS" or m8_status != "PASS":
        decision_reason = "No hay un pronóstico M7 validado ni una decisión M8 aprobada para uso empírico."
    else:
        decision_reason = "Este contrato M9 no convierte resultados de investigación en una orden; requiere una versión que valide plan, restricciones y ejecución manual."

    report = {
        "schema_version": 1,
        "report_version": "1.0.0",
        "revision": 1,
        "report_id": str(uuid4()),
        "report_type": report_type,
        "created_at_utc": _utc(created),
        "as_of_utc": clean["as_of_utc"],
        "decision_status": "NO_TRADE",
        "decision": {
            "action": "NO_TRADE",
            "symbol": None,
            "target_size_actipesos": None,
            "entry_range_actipesos": None,
            "no_pursue_above_actipesos": None,
            "stop_or_invalidation": None,
            "targets_actipesos": None,
            "exit_logic": None,
            "horizon_sessions": None,
            "catalyst": None,
            "probability_estimate": None,
            "confidence": None,
            "estimated_contribution_to_p1": None,
            "summary_reason": decision_reason,
            "risks": sorted(set(reasons)),
            "execution_mode": "MANUAL_ONLY",
        },
        "competition": deepcopy(clean["competition"]),
        "portfolio": deepcopy(clean["portfolio"]),
        "evidence": {
            "m1_symbol_mapping": {"status": "UNVERIFIED", "detail": "El mapeo de símbolos de la plataforma no está autenticado."},
            "m7": {"status": m7_status, "detail": m7_reason, "sha256": m7_sha256},
            "m8": {"status": m8_status, "detail": m8_reason, "sha256": m8_sha256},
            "freshness": freshness,
            "events": "AVAILABLE" if event_rows else "NOT_SUPPLIED",
            "event_snapshot_digests": event_sources,
        },
        "material_events": event_rows,
        "provenance": {
            "context_id": clean["context_id"],
            "context_sha256": context_sha256 or canonical_sha256(clean),
            "source_files": [
                {"source_id": source["snapshot_id"], "sha256": source["file_sha256"]}
                for source in event_sources
            ],
            "m7_result_sha256": m7_sha256,
            "m8_result_sha256": m8_sha256,
            "event_snapshot_sha256": [item.get("file_sha256", item["sha256"]) for item in event_sources],
        },
        "operator_note": "Este documento no es una orden ni una instrucción de compra/venta. No automatiza el portal Actinver.",
    }
    # Defensive invariant: an M9 report may not silently become an executable recommendation.
    if report["decision"]["action"] != "NO_TRADE" or report["decision_status"] != "NO_TRADE":
        raise TradeSheetError("internal safety invariant violated: reports must remain NO_TRADE")
    return report


def _read_audit(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TradeSheetError(f"cannot read audit log {path}: {exc}") from exc
    if not raw:
        return [], None
    if not raw.endswith(b"\n"):
        raise TradeSheetError("audit log has a truncated final line")
    rows: list[dict[str, Any]] = []
    previous: str | None = None
    seen: set[str] = set()
    for number, line in enumerate(raw.splitlines(), start=1):
        try:
            row = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise TradeSheetError(f"audit log line {number} is invalid: {exc}") from exc
        _object(row, {"event_id", "occurred_at_utc", "event_type", "object_id", "object_sha256", "previous_event_sha256", "event_sha256"}, set(), f"audit log line {number}")
        _text(row["event_id"], f"audit log line {number}.event_id")
        if row["event_id"] in seen:
            raise TradeSheetError(f"audit log line {number} repeats event_id {row['event_id']!r}")
        seen.add(row["event_id"])
        _instant(row["occurred_at_utc"], f"audit log line {number}.occurred_at_utc")
        if row["event_type"] not in AUDIT_EVENT_TYPES:
            raise TradeSheetError(f"audit log line {number} has an unsupported event_type")
        _text(row["object_id"], f"audit log line {number}.object_id")
        for digest_name in ("object_sha256", "event_sha256"):
            if type(row[digest_name]) is not str or not SHA256_RE.fullmatch(row[digest_name]):
                raise TradeSheetError(f"audit log line {number}.{digest_name} is not a SHA-256 digest")
        if row["previous_event_sha256"] != previous:
            raise TradeSheetError(f"audit log line {number} breaks the previous-event hash link")
        body = {key: value for key, value in row.items() if key != "event_sha256"}
        if canonical_sha256(body) != row["event_sha256"]:
            raise TradeSheetError(f"audit log line {number} does not match its event hash")
        rows.append(row)
        previous = row["event_sha256"]
    return rows, previous


@contextmanager
def _lock_file(path: Path) -> Iterator[None]:
    """Serialize local audit writers using a portable sidecar lock."""
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def append_audit_event(path: Path, *, event_type: str, object_id: str, object_sha256: str, occurred_at: datetime | None = None) -> dict[str, Any]:
    if event_type not in AUDIT_EVENT_TYPES:
        raise TradeSheetError(f"unsupported audit event type {event_type!r}")
    if not SHA256_RE.fullmatch(object_sha256):
        raise TradeSheetError("object_sha256 must be a lowercase SHA-256 digest")
    with _lock_file(path):
        rows, previous = _read_audit(path)
        if any(row["object_id"] == object_id and row["event_type"] == event_type for row in rows):
            raise TradeSheetError(f"audit log already contains {event_type} for {object_id}")
        event: dict[str, Any] = {
            "event_id": str(uuid4()),
            "occurred_at_utc": _utc((occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)),
            "event_type": event_type,
            "object_id": _text(object_id, "object_id"),
            "object_sha256": object_sha256,
            "previous_event_sha256": previous,
        }
        event["event_sha256"] = canonical_sha256(event)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        try:
            with path.open("ab") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise TradeSheetError(f"cannot append audit log {path}: {exc}") from exc
        # Read-after-write confirms that storage did not truncate or interleave this line.
        _read_audit(path)
        return event


def verify_audit_log(path: Path) -> dict[str, Any]:
    rows, tail = _read_audit(path)
    return {"valid": True, "event_count": len(rows), "head_event_sha256": rows[0]["event_sha256"] if rows else None, "tail_event_sha256": tail, "events": rows}


def write_json_atomic(value: Any, path: Path) -> None:
    try:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise TradeSheetError(f"refusing to overwrite existing output {path}")
        temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
        temporary.write_text(rendered, encoding="utf-8", newline="\n")
        try:
            os.replace(temporary, path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise
    except (OSError, TypeError, ValueError) as exc:
        if isinstance(exc, TradeSheetError):
            raise
        raise TradeSheetError(f"cannot write JSON to {path}: {exc}") from exc


def create_trade_sheet(context: Any, *, report_type: str, output_dir: Path, audit_path: Path,
                       m7_result: Any | None = None, m7_sha256: str | None = None,
                       m8_result: Any | None = None, m8_sha256: str | None = None,
                       event_snapshots: list[Any] | None = None,
                       context_sha256: str | None = None,
                       event_snapshot_sha256: list[str] | None = None) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    report = build_trade_sheet(context, report_type=report_type, m7_result=m7_result, m7_sha256=m7_sha256,
                               m8_result=m8_result, m8_sha256=m8_sha256, event_snapshots=event_snapshots,
                               context_sha256=context_sha256, event_snapshot_sha256=event_snapshot_sha256)
    suffix = report["created_at_utc"].replace(":", "").replace("-", "")
    output_path = output_dir / f"{report_type}_{suffix}_{report['report_id']}.json"
    write_json_atomic(report, output_path)
    report_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    event = append_audit_event(audit_path, event_type="TRADE_SHEET_CREATED", object_id=report["report_id"], object_sha256=report_sha)
    return report, output_path, event


def build_post_trade_attribution(activity: Any, trade_sheet: Any, *, report_sha256: str | None = None,
                                 created_at: datetime | None = None) -> dict[str, Any]:
    item = _object(activity, {"schema_version", "activity_id", "report_id", "captured_at_utc", "starting_capital_actipesos", "ending_capital_actipesos", "net_external_flows_actipesos", "manual_fills", "source_reference"}, set(), "activity")
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise TradeSheetError("activity.schema_version must equal 1")
    _text(item["activity_id"], "activity.activity_id")
    captured = _instant(item["captured_at_utc"], "activity.captured_at_utc")
    _text(item["source_reference"], "activity.source_reference")
    if type(trade_sheet) is not dict or trade_sheet.get("schema_version") != 1:
        raise TradeSheetError("trade_sheet must be a version 1 M9 report")
    if trade_sheet.get("decision_status") != "NO_TRADE" or type(trade_sheet.get("decision")) is not dict or trade_sheet["decision"].get("action") != "NO_TRADE":
        raise TradeSheetError("post-trade attribution requires an M9 NO_TRADE report")
    if type(trade_sheet.get("report_id")) is not str or not trade_sheet["report_id"]:
        raise TradeSheetError("trade_sheet.report_id must be a non-empty string")
    if item["report_id"] != trade_sheet.get("report_id"):
        raise TradeSheetError("activity report_id does not match the linked trade sheet")
    start = _number(item["starting_capital_actipesos"], "activity.starting_capital_actipesos", minimum=0)
    end = _number(item["ending_capital_actipesos"], "activity.ending_capital_actipesos", minimum=0)
    flows = _number(item["net_external_flows_actipesos"], "activity.net_external_flows_actipesos")
    assert start is not None and end is not None and flows is not None
    if type(item["manual_fills"]) is not list:
        raise TradeSheetError("activity.manual_fills must be an array")
    fill_ids: set[str] = set()
    notional = Decimal("0")
    fees = Decimal("0")
    fill_times = []
    for index, raw_fill in enumerate(item["manual_fills"]):
        fill = _object(raw_fill, {"fill_id", "instrument_id", "side", "quantity", "price_actipesos", "fees_actipesos", "executed_at_utc"}, set(), f"activity.manual_fills[{index}]")
        fill_id = _text(fill["fill_id"], f"activity.manual_fills[{index}].fill_id")
        if fill_id in fill_ids:
            raise TradeSheetError(f"activity.manual_fills duplicates fill_id {fill_id!r}")
        fill_ids.add(fill_id)
        _text(fill["instrument_id"], f"activity.manual_fills[{index}].instrument_id")
        if fill["side"] not in {"BUY", "SELL"}:
            raise TradeSheetError(f"activity.manual_fills[{index}].side must be BUY or SELL")
        qty = _number(fill["quantity"], f"activity.manual_fills[{index}].quantity", minimum=0)
        price = _number(fill["price_actipesos"], f"activity.manual_fills[{index}].price_actipesos", minimum=0)
        fee = _number(fill["fees_actipesos"], f"activity.manual_fills[{index}].fees_actipesos", minimum=0)
        assert qty is not None and price is not None and fee is not None
        if qty <= 0 or price <= 0:
            raise TradeSheetError(f"activity.manual_fills[{index}] quantity and price must be greater than zero")
        notional += Decimal(str(qty)) * Decimal(str(price))
        fees += Decimal(str(fee))
        fill_times.append(_instant(fill["executed_at_utc"], f"activity.manual_fills[{index}].executed_at_utc"))
    sheet_created = _instant(trade_sheet.get("created_at_utc"), "trade_sheet.created_at_utc")
    if sheet_created is not None and any(time is not None and time < sheet_created for time in fill_times):
        raise TradeSheetError("manual fill predates the linked trade sheet")
    if any(time is not None and time > captured for time in fill_times):
        raise TradeSheetError("manual fill occurs after the activity capture time")
    net_change_decimal = Decimal(str(end)) - Decimal(str(start)) - Decimal(str(flows))
    net_change = float(net_change_decimal)
    created = created_at or datetime.now(timezone.utc)
    if created.tzinfo is None or created.utcoffset() is None:
        raise TradeSheetError("created_at must include a UTC offset")
    if captured is not None and captured > created.astimezone(timezone.utc):
        raise TradeSheetError("captured_at_utc cannot be later than attribution creation")
    linked_report_sha = report_sha256 or canonical_sha256(trade_sheet)
    if not SHA256_RE.fullmatch(linked_report_sha):
        raise TradeSheetError("report_sha256 must be a lowercase SHA-256 digest")
    return {
        "schema_version": 1,
        "attribution_version": "1.0.0",
        "attribution_id": str(uuid4()),
        "report_id": item["report_id"],
        "report_sha256": linked_report_sha,
        "activity_id": item["activity_id"],
        "created_at_utc": _utc(created),
        "captured_at_utc": item["captured_at_utc"],
        "source_reference": item["source_reference"],
        "starting_capital_actipesos": start,
        "ending_capital_actipesos": end,
        "net_external_flows_actipesos": flows,
        "net_portfolio_change_actipesos": net_change,
        "net_portfolio_return": float(net_change_decimal / Decimal(str(start))) if start > 0 else None,
        "manual_fill_count": len(item["manual_fills"]),
        "manual_fill_notional_actipesos": float(notional),
        "reported_fees_actipesos": float(fees),
        "linked_m9_action": trade_sheet.get("decision", {}).get("action", "UNKNOWN"),
        "activity_vs_m9": "NO_FILL_REPORTED" if not fill_ids else "MANUAL_ACTIVITY_WITHOUT_VALIDATED_M9_INSTRUCTION",
        "causal_strategy_contribution_actipesos": None,
        "p_final_rank_1_contribution": None,
        "attribution_status": "DESCRIPTIVE_ONLY",
        "limitations": [
            "Portfolio change is an accounting difference from operator-supplied balances, net of reported external flows.",
            "Manual fills, fees, and balance sources are not authenticated by a broker connection.",
            "No-trade counterfactual prices and complete point-in-time leaderboard outcomes were not supplied; causal strategy contribution and P(final_rank=1) contribution are null.",
        ],
    }


def create_post_trade_attribution(activity: Any, trade_sheet: Any, *, output_path: Path, audit_path: Path,
                                  report_sha256: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    attribution = build_post_trade_attribution(activity, trade_sheet, report_sha256=report_sha256)
    write_json_atomic(attribution, output_path)
    attribution_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    event = append_audit_event(audit_path, event_type="POST_TRADE_ATTRIBUTION_CREATED", object_id=attribution["attribution_id"], object_sha256=attribution_sha)
    return attribution, event
