"""Point-in-time news/event normalization, feature extraction contracts, and evaluation.

This module never calls an LLM or a news provider. It accepts source documents
and separately supplied structured extractions so licensed ingestion and model
execution can remain outside the repository. Future-return labels are handled
by a different function and are never included in extraction inputs.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .data_engine import DataEngineError, query_as_of


class NewsEventError(ValueError):
    """Raised when a news source, event extraction, label, or evaluation is unsafe."""


NEWS_EVENT_TYPES = {
    "earnings_release",
    "earnings_guidance",
    "revenue_guidance",
    "dividend",
    "merger_acquisition",
    "capital_raise",
    "regulatory",
    "litigation",
    "product_launch",
    "management_change",
    "macro_policy",
    "macro_data",
    "fx_commodity",
    "index_rebalance",
    "trading_halt",
    "actinver_rule_change",
    "other",
}
_SOURCE_QUALITY = {"primary_official", "primary_issuer", "secondary_reputable", "unverified"}
_REDISTRIBUTION = {"permitted", "restricted", "unknown"}
_DIRECTIONS = {"positive", "negative", "mixed", "neutral", "unknown"}
_GUIDANCE_DIRECTIONS = {"positive", "negative", "mixed", "no_guidance", "unknown"}
_MATCH_STATUSES = {"MATCHED", "AMBIGUOUS", "UNMAPPED"}
_SPLITS = ("train", "validation", "test")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_NEWS_DOCUMENT_FIELDS = {
    "schema_version", "document_id", "revision_id", "source_id", "publisher",
    "first_public_time", "revision_public_time", "ingestion_time", "event_time",
    "source_url", "source_type", "redistribution_status", "source_quality", "title", "body",
}
_NORMALIZED_DOCUMENT_FIELDS = _NEWS_DOCUMENT_FIELDS | {"content_sha256", "duplicate_group_id"}
_SNAPSHOT_FIELDS = {
    "schema_version", "snapshot_id", "source_id", "publisher", "document_id", "revision_id",
    "source_content_sha256", "duplicate_group_id", "first_public_time", "revision_public_time",
    "source_ingestion_time", "source_url", "source_type", "redistribution_status", "source_quality",
    "extraction_version", "extraction_model", "prompt_sha256", "extraction_completed_at",
    "feature_available_time", "ingestion_time", "events",
}
_EXTRACTED_EVENT_FIELDS = {
    "event_type", "event_time", "entity_mentions", "novelty", "direction", "surprise_magnitude",
    "guidance_direction", "materiality", "confidence", "affected_sectors", "links",
}
_EVENT_FIELDS = {
    "event_ordinal", "event_group_id", "event_type", "event_time", "entities", "novelty", "direction",
    "surprise_magnitude", "guidance_direction", "materiality", "confidence", "affected_sectors", "links",
}
_EVALUATION_FIELDS = {
    "schema_version", "evaluation_id", "target_definition", "horizon_sessions", "baseline_description",
    "train_period", "validation_period", "test_period", "final_holdout_locked", "test_used_for_selection",
    "evidence", "observations",
}
_EVIDENCE_FIELDS = {
    "data_status", "source_availability_verified", "instrument_mapping_verified", "prices_authorized",
    "execution_costs_verified",
}
_OBSERVATION_FIELDS = {
    "event_id", "event_group_id", "instrument_id", "feature_available_time", "prediction_available_time",
    "decision_time", "label_available_time", "label_id", "split", "forward_return", "event_probability",
}


def _canonical(value: Any) -> bytes:
    try:
        return (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NewsEventError(f"value is not canonical JSON: {exc}") from exc


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise NewsEventError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _object(value: Any, field: str, required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise NewsEventError(f"{field} must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise NewsEventError(f"{field} is missing fields: {', '.join(missing)}")
    if unknown:
        raise NewsEventError(f"{field} has unknown fields: {', '.join(unknown)}")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NewsEventError(f"{field} must be non-empty text")
    return value.strip()


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise NewsEventError(f"{field} has an unsupported value")
    return value


def _timestamp(value: Any, field: str) -> tuple[datetime, str]:
    if not isinstance(value, str) or not value.strip():
        raise NewsEventError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise NewsEventError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NewsEventError(f"{field} must include a timezone offset")
    normalized = parsed.astimezone(timezone.utc)
    # Fixed-width UTC timestamps preserve lexical ordering at sub-second
    # boundaries (e.g. an integer second versus one with fractional seconds).
    return normalized, normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _optional_timestamp(value: Any, field: str) -> tuple[datetime | None, str | None]:
    if value is None:
        return None, None
    return _timestamp(value, field)


def _decimal(value: Any, field: str, *, minimum: Decimal | None = None, maximum: Decimal | None = None) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise NewsEventError(f"{field} must be an exact decimal string or integer")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise NewsEventError(f"{field} must be a valid decimal") from exc
    if not parsed.is_finite() or (minimum is not None and parsed < minimum) or (maximum is not None and parsed > maximum):
        bounds = f" in [{minimum}, {maximum}]" if minimum is not None and maximum is not None else " within its allowed range"
        raise NewsEventError(f"{field} must be finite{bounds}")
    return parsed


def _probability(value: Any, field: str) -> Decimal:
    return _decimal(value, field, minimum=Decimal(0), maximum=Decimal(1))


def _safe_url(value: Any, field: str) -> str:
    url = _text(value, field)
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise NewsEventError(f"{field} must be a valid HTTP(S) URL") from exc
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or hostname is None
        or (port is not None and not 1 <= port <= 65535)
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise NewsEventError(f"{field} must be an HTTP(S) URL without credentials, query strings, or fragments")
    return url


def _text_fingerprint(title: str, body: str) -> str:
    normalize = lambda value: " ".join(unicodedata.normalize("NFC", value).split())
    return hashlib.sha256(_canonical({"title": normalize(title), "body": normalize(body)})).hexdigest()


def normalize_news_documents(rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Validate article provenance and conservatively deduplicate identical source revisions."""
    versions: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicate_count = 0
    for index, raw in enumerate(rows):
        item = _object(raw, f"documents[{index}]", _NEWS_DOCUMENT_FIELDS)
        if type(item["schema_version"]) is not int or item["schema_version"] != 1:
            raise NewsEventError(f"documents[{index}].schema_version must equal 1")
        for field in ("document_id", "revision_id", "source_id", "publisher", "source_type", "title", "body"):
            _text(item[field], f"documents[{index}].{field}")
        if len(item["body"]) > 2_000_000:
            raise NewsEventError(f"documents[{index}].body exceeds the 2 MB text limit")
        _enum(item["redistribution_status"], f"documents[{index}].redistribution_status", _REDISTRIBUTION)
        _enum(item["source_quality"], f"documents[{index}].source_quality", _SOURCE_QUALITY)
        first_public, first_public_text = _timestamp(item["first_public_time"], f"documents[{index}].first_public_time")
        revision_public, revision_public_text = _timestamp(item["revision_public_time"], f"documents[{index}].revision_public_time")
        ingested, ingested_text = _timestamp(item["ingestion_time"], f"documents[{index}].ingestion_time")
        event_time, event_time_text = _optional_timestamp(item["event_time"], f"documents[{index}].event_time")
        if revision_public < first_public:
            raise NewsEventError(f"documents[{index}].revision_public_time cannot precede first_public_time")
        if ingested < revision_public:
            raise NewsEventError(f"documents[{index}].ingestion_time cannot precede revision_public_time")
        normalized = {
            "schema_version": 1,
            "document_id": item["document_id"].strip(),
            "revision_id": item["revision_id"].strip(),
            "source_id": item["source_id"].strip(),
            "publisher": item["publisher"].strip(),
            "first_public_time": first_public_text,
            "revision_public_time": revision_public_text,
            "ingestion_time": ingested_text,
            "event_time": event_time_text,
            "source_url": _safe_url(item["source_url"], f"documents[{index}].source_url"),
            "source_type": item["source_type"].strip(),
            "redistribution_status": item["redistribution_status"],
            "source_quality": item["source_quality"],
            "title": item["title"].strip(),
            "body": item["body"].strip(),
        }
        content_sha = _text_fingerprint(normalized["title"], normalized["body"])
        normalized["content_sha256"] = content_sha
        normalized["duplicate_group_id"] = content_sha
        key = (normalized["source_id"], normalized["document_id"], normalized["revision_id"])
        previous = versions.get(key)
        if previous is None:
            versions[key] = normalized
            continue
        previous_content = {field: value for field, value in previous.items() if field != "ingestion_time"}
        current_content = {field: value for field, value in normalized.items() if field != "ingestion_time"}
        if previous_content != current_content:
            raise NewsEventError("conflicting values share source_id, document_id, and revision_id")
        if normalized["ingestion_time"] < previous["ingestion_time"]:
            versions[key] = normalized
        duplicate_count += 1
    normalized_rows = sorted(
        versions.values(),
        key=lambda row: (row["source_id"], row["document_id"], row["revision_public_time"], row["revision_id"]),
    )
    publication_versions: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in normalized_rows:
        key = (row["source_id"], row["document_id"], row["revision_public_time"])
        previous = publication_versions.get(key)
        if previous is not None and previous["content_sha256"] != row["content_sha256"]:
            raise NewsEventError("different document revisions share a source publication timestamp")
        publication_versions[key] = row
    return normalized_rows, duplicate_count


def query_news_documents_as_of(
    documents: Iterable[Mapping[str, Any]], as_of: str, *, mode: str = "source"
) -> list[dict[str, Any]]:
    """Return the latest article revision knowable at a source or system cutoff."""
    if mode not in ("source", "system"):
        raise NewsEventError("mode must be 'source' or 'system'")
    cutoff, cutoff_text = _timestamp(as_of, "as_of")
    raw_documents = []
    for index, raw in enumerate(documents):
        if isinstance(raw, Mapping) and set(raw) == _NORMALIZED_DOCUMENT_FIELDS:
            source_fields = {key: raw[key] for key in _NEWS_DOCUMENT_FIELDS}
            normalized_one, _ = normalize_news_documents([source_fields])
            if (
                normalized_one[0]["content_sha256"] != raw["content_sha256"]
                or normalized_one[0]["duplicate_group_id"] != raw["duplicate_group_id"]
            ):
                raise NewsEventError(f"documents[{index}] content fingerprint does not match its text")
            raw_documents.append(source_fields)
        else:
            raw_documents.append(raw)
    rows, _duplicates = normalize_news_documents(raw_documents)
    visible = []
    for row in rows:
        public_time, _ = _timestamp(row["revision_public_time"], "revision_public_time")
        ingested, _ = _timestamp(row["ingestion_time"], "ingestion_time")
        if public_time > cutoff or (mode == "system" and ingested > cutoff):
            continue
        visible.append(row)
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in visible:
        key = (row["source_id"], row["document_id"])
        previous = latest.get(key)
        if previous is None or row["revision_public_time"] > previous["revision_public_time"]:
            latest[key] = row
        elif row["revision_public_time"] == previous["revision_public_time"] and row != previous:
            raise NewsEventError(f"conflicting article revisions are visible at {cutoff_text}")
    return sorted(latest.values(), key=lambda row: (row["revision_public_time"], row["source_id"], row["document_id"]))


def _validate_normalized_document(value: Any, field: str) -> dict[str, Any]:
    """Recompute derived fingerprints before a normalized document is trusted."""
    item = _object(dict(value), field, _NORMALIZED_DOCUMENT_FIELDS)
    raw = {key: item[key] for key in _NEWS_DOCUMENT_FIELDS}
    normalized, _duplicates = normalize_news_documents([raw])
    if normalized[0] != item:
        raise NewsEventError(f"{field} does not match the normalized source document and fingerprints")
    return normalized[0]


def build_entity_catalog(universe: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build exact-match guide-symbol and issuer-name aliases from the M1 snapshot."""
    instruments = universe.get("instruments") if isinstance(universe, Mapping) else None
    if not isinstance(instruments, list):
        raise NewsEventError("universe.instruments must be an array")
    issuer_instruments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    catalog: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, instrument in enumerate(instruments):
        if not isinstance(instrument, dict):
            raise NewsEventError(f"universe.instruments[{index}] must be an object")
        instrument_id = _text(instrument.get("instrument_id"), f"universe.instruments[{index}].instrument_id")
        issuer_key = _text(instrument.get("issuer_key"), f"universe.instruments[{index}].issuer_key")
        eligibility = instrument.get("eligibility", {})
        if not isinstance(eligibility, Mapping):
            raise NewsEventError(f"universe.instruments[{index}].eligibility must be an object")
        issuer_instruments[issuer_key].append(instrument)
        alias = _alias_key(instrument.get("guide_symbol"))
        if alias:
            platform_verified = (
                eligibility.get("platform_search_symbol_verified") is True
                and isinstance(instrument.get("platform_symbol"), str)
                and isinstance(instrument.get("series"), str)
            )
            candidate = {
                "entity_kind": "instrument",
                "entity_id": instrument_id,
                "instrument_ids": [instrument_id],
                "platform_mapping_verified": platform_verified,
            }
            # Added after collecting issuers below; retain symbol candidates now.
            catalog[alias].append(candidate)
    # Guide names map to source-local issuers. A guide symbol may still be
    # unusable in the competition simulator; that separate state is retained.
    for issuer_key, rows in issuer_instruments.items():
        name_aliases = {_alias_key(row.get("issuer_or_name")) for row in rows}
        for alias in name_aliases - {""}:
            platform_verified = all(
                row.get("eligibility", {}).get("platform_search_symbol_verified") is True
                and isinstance(row.get("platform_symbol"), str)
                and isinstance(row.get("series"), str)
                for row in rows
            )
            catalog[alias].append({
                "entity_kind": "issuer",
                "entity_id": issuer_key,
                "instrument_ids": sorted(row["instrument_id"] for row in rows),
                "platform_mapping_verified": platform_verified,
            })
    for alias, candidates in catalog.items():
        unique = {(_canonical(candidate)): candidate for candidate in candidates}
        catalog[alias] = [unique[key] for key in sorted(unique)]
    return catalog


def _alias_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def map_entity_mentions(mentions: Iterable[str], catalog: Mapping[str, list[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    mapped = []
    for index, raw in enumerate(mentions):
        mention = _text(raw, f"entity_mentions[{index}]")
        candidates = catalog.get(_alias_key(mention), [])
        unique = {(_canonical(dict(candidate))): dict(candidate) for candidate in candidates}
        candidates = [unique[key] for key in sorted(unique)]
        if not candidates:
            mapped.append({
                "mention": mention,
                "match_status": "UNMAPPED",
                "entity_kind": "unresolved",
                "entity_id": None,
                "candidate_entity_ids": [],
                "instrument_ids": [],
                "platform_mapping_verified": False,
            })
            continue
        ids = sorted({candidate["entity_id"] for candidate in candidates})
        if len(ids) != 1:
            mapped.append({
                "mention": mention,
                "match_status": "AMBIGUOUS",
                "entity_kind": "unresolved",
                "entity_id": None,
                "candidate_entity_ids": ids,
                "instrument_ids": sorted({item for candidate in candidates for item in candidate["instrument_ids"]}),
                "platform_mapping_verified": False,
            })
            continue
        selected = candidates[0]
        mapped.append({
            "mention": mention,
            "match_status": "MATCHED",
            "entity_kind": selected["entity_kind"],
            "entity_id": selected["entity_id"],
            "candidate_entity_ids": ids,
            "instrument_ids": sorted(set(selected["instrument_ids"])),
            "platform_mapping_verified": selected["platform_mapping_verified"],
        })
    return mapped


def build_extraction_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return article-only material for an extractor; no labels or market data enter this API."""
    item = _validate_normalized_document(document, "document")
    return {
        "document_id": item["document_id"],
        "revision_id": item["revision_id"],
        "source_id": item["source_id"],
        "publisher": item["publisher"],
        "first_public_time": item["first_public_time"],
        "revision_public_time": item["revision_public_time"],
        "source_url": item["source_url"],
        "source_quality": item["source_quality"],
        "title": item["title"],
        "body": item["body"],
        "source_content_sha256": item["content_sha256"],
        "instructions": "Extract structured facts from this source only. Do not infer trades, prices, returns, or information absent from the document.",
    }


def _normalize_entity_mapping(value: Any, field: str) -> dict[str, Any]:
    item = _object(value, field, {
        "mention", "match_status", "entity_kind", "entity_id", "candidate_entity_ids", "instrument_ids",
        "platform_mapping_verified",
    })
    _text(item["mention"], f"{field}.mention")
    _enum(item["match_status"], f"{field}.match_status", _MATCH_STATUSES)
    if not isinstance(item["candidate_entity_ids"], list) or any(not isinstance(x, str) or not x.strip() for x in item["candidate_entity_ids"]):
        raise NewsEventError(f"{field}.candidate_entity_ids must contain non-empty strings")
    if not isinstance(item["instrument_ids"], list) or any(not isinstance(x, str) or not x.strip() for x in item["instrument_ids"]):
        raise NewsEventError(f"{field}.instrument_ids must contain non-empty strings")
    if type(item["platform_mapping_verified"]) is not bool:
        raise NewsEventError(f"{field}.platform_mapping_verified must be boolean")
    if item["match_status"] == "MATCHED":
        if item["entity_kind"] not in ("issuer", "instrument"):
            raise NewsEventError(f"{field}.entity_kind must be issuer or instrument for a matched entity")
        _text(item["entity_id"], f"{field}.entity_id")
        if item["candidate_entity_ids"] != [item["entity_id"]]:
            raise NewsEventError(f"{field} matched entity candidates do not agree")
        if not item["instrument_ids"] or len(set(item["instrument_ids"])) != len(item["instrument_ids"]):
            raise NewsEventError(f"{field}.instrument_ids must be non-empty and unique for a matched entity")
    else:
        if item["entity_kind"] != "unresolved" or item["entity_id"] is not None or item["platform_mapping_verified"]:
            raise NewsEventError(f"{field} unresolved mapping cannot assert an entity or verified platform mapping")
        candidates = item["candidate_entity_ids"]
        if candidates != sorted(set(candidates)):
            raise NewsEventError(f"{field}.candidate_entity_ids must be sorted and unique")
        if item["match_status"] == "AMBIGUOUS" and len(candidates) < 2:
            raise NewsEventError(f"{field} ambiguous mapping needs multiple candidates")
        if item["match_status"] == "UNMAPPED" and (candidates or item["instrument_ids"]):
            raise NewsEventError(f"{field} unmapped entity cannot include candidates or instrument IDs")
    return item


def _normalize_extracted_event(value: Any, index: int, catalog: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    item = _object(value, f"extraction.events[{index}]", _EXTRACTED_EVENT_FIELDS)
    _enum(item["event_type"], f"extraction.events[{index}].event_type", NEWS_EVENT_TYPES)
    event_time, event_time_text = _optional_timestamp(item["event_time"], f"extraction.events[{index}].event_time")
    mentions = item["entity_mentions"]
    if not isinstance(mentions, list) or any(not isinstance(mention, str) or not mention.strip() for mention in mentions):
        raise NewsEventError(f"extraction.events[{index}].entity_mentions must contain non-empty strings")
    _enum(item["direction"], f"extraction.events[{index}].direction", _DIRECTIONS)
    _enum(item["guidance_direction"], f"extraction.events[{index}].guidance_direction", _GUIDANCE_DIRECTIONS)
    decimals = {
        "novelty": str(_probability(item["novelty"], f"extraction.events[{index}].novelty")),
        "materiality": str(_probability(item["materiality"], f"extraction.events[{index}].materiality")),
        "confidence": str(_probability(item["confidence"], f"extraction.events[{index}].confidence")),
        "surprise_magnitude": (
            str(_probability(item["surprise_magnitude"], f"extraction.events[{index}].surprise_magnitude"))
            if item["surprise_magnitude"] is not None else None
        ),
    }
    sectors = item["affected_sectors"]
    if not isinstance(sectors, list) or any(not isinstance(sector, str) or not sector.strip() for sector in sectors):
        raise NewsEventError(f"extraction.events[{index}].affected_sectors must contain non-empty strings")
    links = item["links"]
    if not isinstance(links, list):
        raise NewsEventError(f"extraction.events[{index}].links must be an array")
    unique_links = sorted({_safe_url(link, f"extraction.events[{index}].links[]") for link in links})
    return {
        "event_ordinal": index,
        "event_group_id": "",  # Filled after mapping and provenance are bound.
        "event_type": item["event_type"],
        "event_time": event_time_text,
        "entities": [_normalize_entity_mapping(entity, f"extraction.events[{index}].entities[]") for entity in map_entity_mentions(mentions, catalog)],
        **decimals,
        "direction": item["direction"],
        "guidance_direction": item["guidance_direction"],
        "affected_sectors": sorted(set(sector.strip() for sector in sectors)),
        "links": unique_links,
    }


def validate_event_snapshot(value: Any, field: str = "snapshot") -> dict[str, Any]:
    item = _object(value, field, _SNAPSHOT_FIELDS)
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise NewsEventError(f"{field}.schema_version must equal 1")
    for name in ("source_id", "publisher", "document_id", "revision_id", "source_type", "extraction_version", "extraction_model"):
        _text(item[name], f"{field}.{name}")
    _enum(item["redistribution_status"], f"{field}.redistribution_status", _REDISTRIBUTION)
    _enum(item["source_quality"], f"{field}.source_quality", _SOURCE_QUALITY)
    _safe_url(item["source_url"], f"{field}.source_url")
    _sha256(item["source_content_sha256"], f"{field}.source_content_sha256")
    _sha256(item["duplicate_group_id"], f"{field}.duplicate_group_id")
    _sha256(item["prompt_sha256"], f"{field}.prompt_sha256")
    _sha256(item["snapshot_id"], f"{field}.snapshot_id")
    if item["source_content_sha256"] != item["duplicate_group_id"]:
        raise NewsEventError(f"{field} duplicate group must match its normalized content fingerprint")
    first_public, _ = _timestamp(item["first_public_time"], f"{field}.first_public_time")
    revision_public, _ = _timestamp(item["revision_public_time"], f"{field}.revision_public_time")
    source_ingested, _ = _timestamp(item["source_ingestion_time"], f"{field}.source_ingestion_time")
    extracted, _ = _timestamp(item["extraction_completed_at"], f"{field}.extraction_completed_at")
    available, _ = _timestamp(item["feature_available_time"], f"{field}.feature_available_time")
    ingested, _ = _timestamp(item["ingestion_time"], f"{field}.ingestion_time")
    if revision_public < first_public or source_ingested < revision_public:
        raise NewsEventError(f"{field} source publication and ingestion times are inconsistent")
    if extracted < max(revision_public, source_ingested) or available < extracted or ingested < available:
        raise NewsEventError(f"{field}.extraction_completed_at cannot precede source revision/ingestion")
    events = item["events"]
    if not isinstance(events, list):
        raise NewsEventError(f"{field}.events must be an array")
    normalized_events = []
    ordinals = set()
    for index, raw_event in enumerate(events):
        event = _object(raw_event, f"{field}.events[{index}]", _EVENT_FIELDS)
        if type(event["event_ordinal"]) is not int or event["event_ordinal"] < 0 or event["event_ordinal"] in ordinals:
            raise NewsEventError(f"{field}.events[{index}].event_ordinal must be a unique non-negative integer")
        ordinals.add(event["event_ordinal"])
        _sha256(event["event_group_id"], f"{field}.events[{index}].event_group_id")
        _enum(event["event_type"], f"{field}.events[{index}].event_type", NEWS_EVENT_TYPES)
        _optional_timestamp(event["event_time"], f"{field}.events[{index}].event_time")
        _enum(event["direction"], f"{field}.events[{index}].direction", _DIRECTIONS)
        _enum(event["guidance_direction"], f"{field}.events[{index}].guidance_direction", _GUIDANCE_DIRECTIONS)
        for name in ("novelty", "materiality", "confidence"):
            _probability(event[name], f"{field}.events[{index}].{name}")
        if event["surprise_magnitude"] is not None:
            _probability(event["surprise_magnitude"], f"{field}.events[{index}].surprise_magnitude")
        if not isinstance(event["entities"], list):
            raise NewsEventError(f"{field}.events[{index}].entities must be an array")
        for entity in event["entities"]:
            _normalize_entity_mapping(entity, f"{field}.events[{index}].entities[]")
        if not isinstance(event["affected_sectors"], list) or any(not isinstance(x, str) or not x.strip() for x in event["affected_sectors"]):
            raise NewsEventError(f"{field}.events[{index}].affected_sectors must be an array of strings")
        if not isinstance(event["links"], list):
            raise NewsEventError(f"{field}.events[{index}].links must be an array")
        for link in event["links"]:
            _safe_url(link, f"{field}.events[{index}].links[]")
        expected_group = _digest({
            "source_content_sha256": item["source_content_sha256"],
            "event_ordinal": event["event_ordinal"],
            "event_type": event["event_type"],
            "entity_ids": sorted(entity["entity_id"] for entity in event["entities"] if entity["entity_id"] is not None),
            "extraction_version": item["extraction_version"],
        })
        if event["event_group_id"] != expected_group:
            raise NewsEventError(f"{field}.events[{index}].event_group_id does not match its source/event identity")
        normalized_events.append(event)
    body = {key: val for key, val in item.items() if key != "snapshot_id"}
    if hashlib.sha256(_canonical(body)).hexdigest() != item["snapshot_id"]:
        raise NewsEventError(f"{field}.snapshot_id does not match snapshot contents")
    return item


def create_event_snapshot(
    document: Mapping[str, Any],
    extraction: Mapping[str, Any],
    *,
    entity_catalog: Mapping[str, list[Mapping[str, Any]]],
    extraction_version: str,
    extraction_model: str,
    prompt_sha256: str,
    extraction_completed_at: str,
    ingestion_time: str,
) -> dict[str, Any]:
    """Bind a structured extraction to one exact article revision and immutable prompt/model identity."""
    doc = _validate_normalized_document(document, "document")
    extraction_obj = _object(dict(extraction), "extraction", {"events"})
    if not isinstance(extraction_obj["events"], list):
        raise NewsEventError("extraction.events must be an array")
    completed, completed_text = _timestamp(extraction_completed_at, "extraction_completed_at")
    ingest, ingest_text = _timestamp(ingestion_time, "ingestion_time")
    revision, _ = _timestamp(doc["revision_public_time"], "document.revision_public_time")
    source_ingested, _ = _timestamp(doc["ingestion_time"], "document.ingestion_time")
    if completed < max(revision, source_ingested):
        raise NewsEventError("extraction_completed_at cannot precede source revision/ingestion")
    if ingest < completed:
        raise NewsEventError("ingestion_time cannot precede extraction completion")
    extraction_version = _text(extraction_version, "extraction_version")
    extraction_model = _text(extraction_model, "extraction_model")
    prompt_sha256 = _sha256(prompt_sha256, "prompt_sha256")
    events = []
    for index, raw_event in enumerate(extraction_obj["events"]):
        event = _normalize_extracted_event(raw_event, index, entity_catalog)
        event["event_group_id"] = _digest({
            "source_content_sha256": doc["content_sha256"],
            "event_ordinal": index,
            "event_type": event["event_type"],
            "entity_ids": sorted(entity["entity_id"] for entity in event["entities"] if entity["entity_id"] is not None),
            "extraction_version": extraction_version,
        })
        events.append(event)
    snapshot = {
        "schema_version": 1,
        "source_id": doc["source_id"],
        "publisher": doc["publisher"],
        "document_id": doc["document_id"],
        "revision_id": doc["revision_id"],
        "source_content_sha256": doc["content_sha256"],
        "duplicate_group_id": doc["duplicate_group_id"],
        "first_public_time": doc["first_public_time"],
        "revision_public_time": doc["revision_public_time"],
        "source_ingestion_time": doc["ingestion_time"],
        "source_url": doc["source_url"],
        "source_type": doc["source_type"],
        "redistribution_status": doc["redistribution_status"],
        "source_quality": doc["source_quality"],
        "extraction_version": extraction_version,
        "extraction_model": extraction_model,
        "prompt_sha256": prompt_sha256,
        "extraction_completed_at": completed_text,
        "feature_available_time": completed_text,
        "ingestion_time": ingest_text,
        "events": events,
    }
    snapshot["snapshot_id"] = _digest(snapshot)
    return validate_event_snapshot(snapshot)


def prepare_extraction_documents(
    documents: Iterable[Mapping[str, Any]], as_of: str, *, mode: str = "source"
) -> list[dict[str, Any]]:
    """Select one exact-content source item per article cluster before model extraction."""
    visible = query_news_documents_as_of(documents, as_of, mode=mode)
    quality_rank = {"primary_official": 0, "primary_issuer": 1, "secondary_reputable": 2, "unverified": 3}
    selected: dict[str, dict[str, Any]] = {}
    for document in visible:
        group_id = document["duplicate_group_id"]
        previous = selected.get(group_id)
        rank = (document["first_public_time"], quality_rank[document["source_quality"]], document["source_id"], document["document_id"])
        if previous is None:
            selected[group_id] = document
        else:
            previous_rank = (
                previous["first_public_time"], quality_rank[previous["source_quality"]],
                previous["source_id"], previous["document_id"],
            )
            if rank < previous_rank:
                selected[group_id] = document
    return [
        build_extraction_payload(document)
        for document in sorted(selected.values(), key=lambda row: (row["first_public_time"], row["source_id"], row["document_id"]))
    ]


def query_event_snapshots_as_of(
    snapshots: Iterable[Mapping[str, Any]],
    as_of: str,
    *,
    mode: str = "source",
    extraction_version: str | None = None,
) -> list[dict[str, Any]]:
    """Select the latest extraction snapshot knowable by a timestamp."""
    if mode not in ("source", "system"):
        raise NewsEventError("mode must be 'source' or 'system'")
    if extraction_version is not None:
        extraction_version = _text(extraction_version, "extraction_version")
    cutoff, _ = _timestamp(as_of, "as_of")
    visible = []
    for index, raw in enumerate(snapshots):
        snapshot = validate_event_snapshot(dict(raw), f"snapshots[{index}]")
        if extraction_version is not None and snapshot["extraction_version"] != extraction_version:
            continue
        available, _ = _timestamp(snapshot["feature_available_time"], "feature_available_time")
        ingested, _ = _timestamp(snapshot["ingestion_time"], "ingestion_time")
        if available > cutoff or (mode == "system" and ingested > cutoff):
            continue
        visible.append(snapshot)
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for snapshot in visible:
        key = (snapshot["source_id"], snapshot["document_id"], snapshot["extraction_version"])
        previous = latest.get(key)
        revision_public, _ = _timestamp(snapshot["revision_public_time"], "revision_public_time")
        available, _ = _timestamp(snapshot["feature_available_time"], "feature_available_time")
        rank = (revision_public, available)
        previous_rank = (
            (_timestamp(previous["revision_public_time"], "revision_public_time")[0],
             _timestamp(previous["feature_available_time"], "feature_available_time")[0])
            if previous else None
        )
        if previous is None or rank > previous_rank:
            latest[key] = snapshot
        elif rank == previous_rank and snapshot["snapshot_id"] != previous["snapshot_id"]:
            raise NewsEventError("conflicting extraction snapshots have the same revision and feature availability")
    return sorted(
        latest.values(),
        key=lambda row: (row["feature_available_time"], row["source_id"], row["document_id"], row["extraction_version"]),
    )


def flatten_event_snapshots(snapshots: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for snapshot_index, raw in enumerate(snapshots):
        snapshot = validate_event_snapshot(dict(raw), f"snapshots[{snapshot_index}]")
        for event in snapshot["events"]:
            record = deepcopy(event)
            record.update({
                "event_id": _digest({"snapshot_id": snapshot["snapshot_id"], "event_ordinal": event["event_ordinal"]}),
                "snapshot_id": snapshot["snapshot_id"],
                "source_id": snapshot["source_id"],
                "publisher": snapshot["publisher"],
                "document_id": snapshot["document_id"],
                "revision_id": snapshot["revision_id"],
                "source_content_sha256": snapshot["source_content_sha256"],
                "duplicate_group_id": snapshot["duplicate_group_id"],
                "first_public_time": snapshot["first_public_time"],
                "revision_public_time": snapshot["revision_public_time"],
                "source_url": snapshot["source_url"],
                "source_type": snapshot["source_type"],
                "redistribution_status": snapshot["redistribution_status"],
                "source_quality": snapshot["source_quality"],
                "extraction_version": snapshot["extraction_version"],
                "extraction_model": snapshot["extraction_model"],
                "prompt_sha256": snapshot["prompt_sha256"],
                "extraction_completed_at": snapshot["extraction_completed_at"],
                "feature_available_time": snapshot["feature_available_time"],
                "ingestion_time": snapshot["ingestion_time"],
            })
            events.append(record)
    return sorted(events, key=lambda event: (event["feature_available_time"], event["event_id"]))


def _deduplicate_event_stream(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in events:
        group_id = event["event_group_id"]
        previous = grouped.get(group_id)
        if previous is None:
            grouped[group_id] = dict(event)
            continue
        comparable_fields = _EVENT_FIELDS - {"event_group_id"}
        if any(previous.get(field) != event.get(field) for field in comparable_fields):
            raise NewsEventError("duplicate source text produced conflicting event features; preserve a new extraction_version")
        if event["feature_available_time"] < previous["feature_available_time"]:
            grouped[group_id] = dict(event)
    return sorted(grouped.values(), key=lambda event: (event["feature_available_time"], event["event_id"]))


def _timezone(name: str) -> ZoneInfo:
    name = _text(name, "timezone")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise NewsEventError(f"timezone is unknown: {name}") from exc


def build_intelligence_digest(
    snapshots: Iterable[Mapping[str, Any]],
    *,
    window_start: str,
    as_of: str,
    timezone_name: str,
    minimum_materiality: str = "0",
    mode: str = "system",
    extraction_version: str | None = None,
) -> dict[str, Any]:
    """Build a time-bounded morning/overnight digest from available event features."""
    zone = _timezone(timezone_name)
    start, start_text = _timestamp(window_start, "window_start")
    cutoff, cutoff_text = _timestamp(as_of, "as_of")
    if start > cutoff:
        raise NewsEventError("window_start cannot follow the digest cutoff")
    threshold = _probability(minimum_materiality, "minimum_materiality")
    selected_snapshots = query_event_snapshots_as_of(
        snapshots, cutoff_text, mode=mode, extraction_version=extraction_version
    )
    events = _deduplicate_event_stream(flatten_event_snapshots(selected_snapshots))
    in_window = []
    for event in events:
        revision_public, _ = _timestamp(event["revision_public_time"], "revision_public_time")
        materiality = _probability(event["materiality"], "materiality")
        if start <= revision_public <= cutoff and materiality >= threshold:
            local_feature_time = _timestamp(event["feature_available_time"], "feature_available_time")[0].astimezone(zone)
            local_first_public_time = _timestamp(event["first_public_time"], "first_public_time")[0].astimezone(zone)
            local_revision_public_time = revision_public.astimezone(zone)
            in_window.append({
                **event,
                "local_first_public_time": local_first_public_time.isoformat(),
                "local_revision_public_time": local_revision_public_time.isoformat(),
                "local_feature_time": local_feature_time.isoformat(),
            })
    event_counts: dict[str, int] = {}
    for event in in_window:
        event_counts[event["event_type"]] = event_counts.get(event["event_type"], 0) + 1
    return {
        "schema_version": 1,
        "window_start": start_text,
        "as_of": cutoff_text,
        "timezone": timezone_name,
        "mode": mode,
        "extraction_version": extraction_version,
        "minimum_materiality": str(threshold),
        "event_count": len(in_window),
        "counts_by_event_type": dict(sorted(event_counts.items())),
        "events": in_window,
        "decision_boundary": "informational only; this digest does not emit BUY/SELL instructions",
    }


def watch_breaking_events(
    snapshots: Iterable[Mapping[str, Any]],
    *,
    after_time: str,
    after_event_id: str | None,
    as_of: str,
    timezone_name: str,
    minimum_materiality: str = "0.5",
    mode: str = "system",
    extraction_version: str | None = None,
) -> dict[str, Any]:
    """Return material events after a stable (availability time, event id) watermark."""
    zone = _timezone(timezone_name)
    watermark_time, watermark_text = _timestamp(after_time, "after_time")
    if after_event_id is not None:
        _text(after_event_id, "after_event_id")
    cutoff, cutoff_text = _timestamp(as_of, "as_of")
    if watermark_time > cutoff:
        raise NewsEventError("after_time cannot follow as_of")
    threshold = _probability(minimum_materiality, "minimum_materiality")
    selected = query_event_snapshots_as_of(snapshots, cutoff_text, mode=mode, extraction_version=extraction_version)
    events = _deduplicate_event_stream(flatten_event_snapshots(selected))
    output = []
    for event in events:
        available, _ = _timestamp(event["feature_available_time"], "feature_available_time")
        event_key = (available, event["event_id"])
        watermark_key = (watermark_time, after_event_id or "")
        if event_key <= watermark_key or _probability(event["materiality"], "materiality") < threshold:
            continue
        local_time = available.astimezone(zone)
        output.append({**event, "local_feature_time": local_time.isoformat()})
    next_cursor = (
        {"available_time": output[-1]["feature_available_time"], "event_id": output[-1]["event_id"]}
        if output else {"available_time": watermark_text, "event_id": after_event_id}
    )
    return {
        "schema_version": 1,
        "as_of": cutoff_text,
        "timezone": timezone_name,
        "mode": mode,
        "minimum_materiality": str(threshold),
        "events": output,
        "next_cursor": next_cursor,
        "decision_boundary": "alert only; this watcher does not emit BUY/SELL instructions",
    }


def label_forward_returns(
    snapshots: Iterable[Mapping[str, Any]],
    price_records: Iterable[Mapping[str, Any]],
    *,
    horizon_sessions: int,
    label_as_of: str,
    price_dataset_id: str,
    mode: str = "system",
) -> list[dict[str, Any]]:
    """Create separate labels from post-feature M2 bars visible by a declared label cutoff."""
    if type(horizon_sessions) is not int or horizon_sessions < 1:
        raise NewsEventError("horizon_sessions must be a positive integer")
    price_dataset_id = _text(price_dataset_id, "price_dataset_id")
    if mode not in ("source", "system"):
        raise NewsEventError("mode must be 'source' or 'system'")
    try:
        label_cutoff, label_cutoff_text = _timestamp(label_as_of, "label_as_of")
        pit_prices = query_as_of(price_records, label_cutoff_text, mode=mode)
    except (DataEngineError, TypeError) as exc:
        raise NewsEventError(f"price records do not match the M2 PIT contract: {exc}") from exc
    except NewsEventError:
        raise
    price_bars = [row for row in pit_prices if row["record_type"] == "price_bar"]
    bars_by_instrument: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bar in price_bars:
        bars_by_instrument[bar["instrument_id"]].append(bar)
    for rows in bars_by_instrument.values():
        rows.sort(key=lambda row: _timestamp(row["event_time"], "price_bar.event_time")[0])
    output = []
    for event in _deduplicate_event_stream(flatten_event_snapshots(snapshots)):
        feature_available, _ = _timestamp(event["feature_available_time"], "feature_available_time")
        system_available, _ = _timestamp(event["ingestion_time"], "ingestion_time")
        decision = max(feature_available, system_available) if mode == "system" else feature_available
        if label_cutoff <= decision:
            raise NewsEventError(f"label_as_of must follow feature availability for event {event['event_id']}")
        mapped = [
            entity for entity in event["entities"]
            if entity["match_status"] == "MATCHED" and entity["instrument_ids"]
        ]
        instrument_ids = sorted({instrument_id for entity in mapped for instrument_id in entity["instrument_ids"]})
        if not instrument_ids:
            raise NewsEventError(f"event {event['event_id']} has no mapped instrument for forward-return labeling")
        for instrument_id in instrument_ids:
            instrument_bars = bars_by_instrument.get(instrument_id, [])
            sources = {bar["source_id"] for bar in instrument_bars}
            if len(sources) > 1:
                raise NewsEventError("multiple price sources cover one instrument; resolve source precedence before labeling")
            event_times = [_timestamp(bar["event_time"], "price_bar.event_time")[0] for bar in instrument_bars]
            if len(event_times) != len(set(event_times)):
                raise NewsEventError("multiple price records cover one instrument/session; resolve duplicates before labeling")
            eligible = [
                bar for bar in instrument_bars
                if _timestamp(bar["event_time"], "price_bar.event_time")[0] > decision
            ]
            exit_index = horizon_sessions
            if len(eligible) <= exit_index:
                raise NewsEventError(
                    f"event {event['event_id']} has insufficient post-event price bars for {instrument_id} at horizon {horizon_sessions}"
                )
            entry_bar, exit_bar = eligible[0], eligible[exit_index]
            label_available = _timestamp(exit_bar["available_time"], "exit_bar.available_time")[0]
            if mode == "system":
                label_available = max(label_available, _timestamp(exit_bar["ingestion_time"], "exit_bar.ingestion_time")[0])
            if label_available > label_cutoff:
                raise NewsEventError(f"event {event['event_id']} label falls after label_as_of")
            entry_close = _decimal(entry_bar["payload"].get("close"), "entry close", minimum=Decimal("0.0000000001"))
            exit_close = _decimal(exit_bar["payload"].get("close"), "exit close", minimum=Decimal("0.0000000001"))
            with localcontext() as context:
                context.prec = 28
                forward_return = exit_close / entry_close - Decimal(1)
            mapping_verified = all(entity["platform_mapping_verified"] for entity in mapped)
            label_id = _digest({
                "event_id": event["event_id"],
                "instrument_id": instrument_id,
                "price_dataset_id": price_dataset_id,
                "source_id": exit_bar["source_id"],
                "entry_record_id": entry_bar["record_id"],
                "entry_source_revision": entry_bar["source_revision"],
                "entry_close": str(entry_close),
                "exit_record_id": exit_bar["record_id"],
                "exit_source_revision": exit_bar["source_revision"],
                "exit_close": str(exit_close),
                "horizon_sessions": horizon_sessions,
                "label_as_of": label_cutoff_text,
                "mode": mode,
            })
            output.append({
                "schema_version": 1,
                "label_id": label_id,
                "event_id": event["event_id"],
                "event_group_id": event["event_group_id"],
                "instrument_id": instrument_id,
                "price_dataset_id": price_dataset_id,
                "source_id": exit_bar["source_id"],
                "entry_record_id": entry_bar["record_id"],
                "entry_source_revision": entry_bar["source_revision"],
                "label_as_of": label_cutoff_text,
                "decision_time": decision.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                "entry_bar_time": entry_bar["event_time"],
                "entry_close": str(entry_close),
                "exit_record_id": exit_bar["record_id"],
                "exit_source_revision": exit_bar["source_revision"],
                "exit_bar_time": exit_bar["event_time"],
                "exit_close": str(exit_close),
                "horizon_sessions": horizon_sessions,
                "forward_return": format(forward_return, "f"),
                "target_definition": "gross_forward_close_to_close",
                "label_available_time": label_available.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                "label_ingestion_time": exit_bar["ingestion_time"],
                "platform_mapping_verified": mapping_verified,
                "execution_costs_applied": False,
            })
    return sorted(output, key=lambda row: (row["decision_time"], row["event_id"], row["instrument_id"]))


def _validate_period(value: Any, field: str) -> tuple[datetime, datetime, dict[str, str]]:
    item = _object(value, field, {"start", "end"})
    start, start_text = _timestamp(item["start"], f"{field}.start")
    end, end_text = _timestamp(item["end"], f"{field}.end")
    if start > end:
        raise NewsEventError(f"{field}.start must not follow its end")
    return start, end, {"start": start_text, "end": end_text}


def _binary_metrics(rows: list[dict[str, Any]], baseline_probability: Decimal) -> dict[str, Any]:
    if not rows:
        return {
            "event_count": 0,
            "positive_rate": None,
            "baseline_brier_score": None,
            "event_brier_score": None,
            "brier_improvement": None,
            "baseline_log_loss": None,
            "event_log_loss": None,
            "log_loss_improvement": None,
            "expected_calibration_error": None,
            "calibration_bins": [],
        }
    outcomes = [Decimal(1) if Decimal(row["forward_return"]) > 0 else Decimal(0) for row in rows]
    baseline = [baseline_probability] * len(rows)
    event = [Decimal(row["event_probability"]) for row in rows]
    count = Decimal(len(rows))
    baseline_brier = sum((p - outcome) ** 2 for p, outcome in zip(baseline, outcomes)) / count
    event_brier = sum((p - outcome) ** 2 for p, outcome in zip(event, outcomes)) / count
    tiny = Decimal("1e-15")

    def log_loss(probabilities: list[Decimal]) -> Decimal:
        losses = []
        for probability, outcome in zip(probabilities, outcomes):
            p = min(Decimal(1) - tiny, max(tiny, probability))
            losses.append(-(outcome * p.ln() + (Decimal(1) - outcome) * (Decimal(1) - p).ln()))
        return sum(losses) / count

    baseline_log = log_loss(baseline)
    event_log = log_loss(event)
    bins = []
    weighted_calibration_error = Decimal(0)
    for bin_index in range(10):
        low = Decimal(bin_index) / Decimal(10)
        high = Decimal(bin_index + 1) / Decimal(10)
        indices = [
            index for index, probability in enumerate(event)
            if low <= probability < high or (bin_index == 9 and probability == Decimal(1))
        ]
        if not indices:
            continue
        mean_probability = sum(event[index] for index in indices) / Decimal(len(indices))
        observed_rate = sum(outcomes[index] for index in indices) / Decimal(len(indices))
        bin_error = abs(mean_probability - observed_rate)
        weighted_calibration_error += Decimal(len(indices)) / count * bin_error
        bins.append({
            "lower_bound": str(low),
            "upper_bound": str(high),
            "count": len(indices),
            "mean_probability": str(mean_probability),
            "observed_positive_rate": str(observed_rate),
            "absolute_calibration_error": str(bin_error),
        })
    return {
        "event_count": len(rows),
        "positive_rate": str(sum(outcomes) / count),
        "baseline_brier_score": str(baseline_brier),
        "event_brier_score": str(event_brier),
        "brier_improvement": str(baseline_brier - event_brier),
        "baseline_log_loss": str(baseline_log),
        "event_log_loss": str(event_log),
        "log_loss_improvement": str(baseline_log - event_log),
        "expected_calibration_error": str(weighted_calibration_error),
        "calibration_bins": bins,
    }


def evaluate_event_predictions(value: Any) -> dict[str, Any]:
    """Measure supplied event probabilities against a training-only baseline by temporal split.

    This descriptive evaluator does not select model thresholds or promote an
    event feature. Further preregistered robustness, costs, and multiple-testing
    controls belong in the M5 research factory.
    """
    case = _object(value, "evaluation_case", _EVALUATION_FIELDS)
    if type(case["schema_version"]) is not int or case["schema_version"] != 1:
        raise NewsEventError("evaluation_case.schema_version must equal 1")
    _text(case["evaluation_id"], "evaluation_case.evaluation_id")
    if case["target_definition"] != "gross_forward_return_gt_zero":
        raise NewsEventError("evaluation target must be gross_forward_return_gt_zero; net labels need explicit cost modeling")
    if type(case["horizon_sessions"]) is not int or case["horizon_sessions"] < 1:
        raise NewsEventError("evaluation_case.horizon_sessions must be a positive integer")
    _text(case["baseline_description"], "evaluation_case.baseline_description")
    if type(case["final_holdout_locked"]) is not bool or case["final_holdout_locked"] is not True:
        raise NewsEventError("evaluation_case.final_holdout_locked must be true")
    if type(case["test_used_for_selection"]) is not bool or case["test_used_for_selection"]:
        raise NewsEventError("test holdout cannot be used for selection")
    periods = {}
    for split in _SPLITS:
        start, end, normalized = _validate_period(case[f"{split}_period"], f"evaluation_case.{split}_period")
        periods[split] = (start, end, normalized)
    if not (
        periods["train"][1] < periods["validation"][0]
        and periods["validation"][1] < periods["test"][0]
    ):
        raise NewsEventError("train, validation, and test periods must be chronological and non-overlapping")
    evidence = _object(case["evidence"], "evaluation_case.evidence", _EVIDENCE_FIELDS)
    _enum(evidence["data_status"], "evaluation_case.evidence.data_status", {"synthetic_fixture", "authorized_point_in_time", "unverified"})
    for flag in _EVIDENCE_FIELDS - {"data_status"}:
        if type(evidence[flag]) is not bool:
            raise NewsEventError(f"evaluation_case.evidence.{flag} must be boolean")
    observations = case["observations"]
    if not isinstance(observations, list) or not observations:
        raise NewsEventError("evaluation_case.observations must be a non-empty array")
    normalized_rows = []
    training_outcomes = []
    seen_label_ids = set()
    groups_by_split: dict[str, set[str]] = {split: set() for split in _SPLITS}
    for index, raw in enumerate(observations):
        row = _object(raw, f"evaluation_case.observations[{index}]", _OBSERVATION_FIELDS)
        event_id = _text(row["event_id"], f"observations[{index}].event_id")
        group_id = _text(row["event_group_id"], f"observations[{index}].event_group_id")
        instrument_id = _text(row["instrument_id"], f"observations[{index}].instrument_id")
        label_id = _text(row["label_id"], f"observations[{index}].label_id")
        if label_id in seen_label_ids:
            raise NewsEventError(f"duplicate label_id {label_id!r} in evaluation")
        seen_label_ids.add(label_id)
        if row["split"] not in _SPLITS:
            raise NewsEventError(f"observations[{index}].split is unsupported")
        decision, decision_text = _timestamp(row["decision_time"], f"observations[{index}].decision_time")
        feature_available, feature_available_text = _timestamp(
            row["feature_available_time"], f"observations[{index}].feature_available_time"
        )
        label_available, label_text = _timestamp(row["label_available_time"], f"observations[{index}].label_available_time")
        start, end, _period = periods[row["split"]]
        if not start <= decision <= end:
            raise NewsEventError(f"observations[{index}] decision time falls outside its declared split")
        if feature_available > decision:
            raise NewsEventError(f"observations[{index}] event features were not available at the decision time")
        prediction_available, prediction_available_text = _timestamp(
            row["prediction_available_time"], f"observations[{index}].prediction_available_time"
        )
        if prediction_available > decision:
            raise NewsEventError(f"observations[{index}] predictions were not available at the decision time")
        if label_available <= decision:
            raise NewsEventError(f"observations[{index}] label must become available after its decision time")
        if label_available > end:
            raise NewsEventError(f"observations[{index}] label crosses its split boundary; purge/embargo it")
        forward = _decimal(row["forward_return"], f"observations[{index}].forward_return", minimum=Decimal(-1))
        event_probability = _probability(row["event_probability"], f"observations[{index}].event_probability")
        outcome = Decimal(1) if forward > 0 else Decimal(0)
        if row["split"] == "train":
            training_outcomes.append(outcome)
        groups_by_split[row["split"]].add(group_id)
        normalized_rows.append({
            "event_id": event_id,
            "event_group_id": group_id,
            "instrument_id": instrument_id,
            "feature_available_time": feature_available_text,
            "prediction_available_time": prediction_available_text,
            "decision_time": decision_text,
            "label_available_time": label_text,
            "label_id": label_id,
            "split": row["split"],
            "forward_return": str(forward),
            "event_probability": str(event_probability),
        })
    for split_index, split in enumerate(_SPLITS):
        for later in _SPLITS[split_index + 1:]:
            overlap = groups_by_split[split] & groups_by_split[later]
            if overlap:
                raise NewsEventError(f"event groups cross {split}/{later} splits: {', '.join(sorted(overlap))}")
    if not training_outcomes:
        raise NewsEventError("evaluation requires at least one train event to fit the baseline probability")
    training_baseline = sum(training_outcomes) / Decimal(len(training_outcomes))
    metrics = {
        split: _binary_metrics([row for row in normalized_rows if row["split"] == split], training_baseline)
        for split in _SPLITS
    }
    if metrics["test"]["event_count"] == 0:
        raise NewsEventError("evaluation requires at least one final test event")
    evidence_gaps = []
    if evidence["data_status"] != "authorized_point_in_time":
        evidence_gaps.append("authorized point-in-time news/prices are not established")
    for flag, reason in (
        ("source_availability_verified", "source availability is unverified"),
        ("instrument_mapping_verified", "instrument mapping is unverified"),
        ("prices_authorized", "price-data authorization is unverified"),
        ("execution_costs_verified", "execution costs are unverified"),
    ):
        if not evidence[flag]:
            evidence_gaps.append(reason)
    return {
        "schema_version": 1,
        "evaluation_id": case["evaluation_id"],
        "target_definition": case["target_definition"],
        "horizon_sessions": case["horizon_sessions"],
        "baseline_description": case["baseline_description"],
        "training_baseline_probability": str(training_baseline),
        "baseline_fit_split": "train",
        "split_periods": {split: periods[split][2] for split in _SPLITS},
        "train_metrics": metrics["train"],
        "validation_metrics": metrics["validation"],
        "test_metrics": metrics["test"],
        "test_holdout_accessed": True,
        "final_holdout_locked_before_evaluation": case["final_holdout_locked"],
        "test_used_for_selection": False,
        "evidence": evidence,
        "evidence_gaps": evidence_gaps,
        "status_decision": "NEEDS_MORE_EVIDENCE",
        "decision_reason": "descriptive calibration/incremental metrics are not a preregistered, cost-aware scientific promotion",
    }
