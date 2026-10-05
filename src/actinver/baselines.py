"""Small, deterministic reference signals for M4 validation fixtures and research."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from random import Random
from typing import Any, Iterable, Mapping


class BaselineError(ValueError):
    """Raised when a baseline cannot be built from point-in-time records."""


BASELINE_NAMES = (
    "random_control",
    "equal_weight",
    "benchmark",
    "momentum",
    "relative_strength",
    "abnormal_volume",
    "reversal",
    "breakout_volatility_expansion",
)

_UTC = timezone.utc


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise BaselineError(f"{field} must be an exact decimal string or integer")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BaselineError(f"{field} must be a valid decimal") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise BaselineError(f"{field} must be finite and {'positive' if positive else 'non-negative'}")
    return result


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise BaselineError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise BaselineError(f"{field} must include a UTC offset")
    return result.astimezone(_UTC)


def _visible_records(
    records: Iterable[Mapping[str, Any]],
    instrument_ids: set[str],
    cutoff: datetime,
    as_of_mode: str,
) -> dict[str, list[dict[str, Any]]]:
    if as_of_mode not in {"source", "system"}:
        raise BaselineError("as_of_mode must be source or system")
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise BaselineError(f"records[{index}] must be an object")
        if record.get("record_type") != "price_bar":
            continue
        instrument_id = record.get("instrument_id")
        if instrument_id not in instrument_ids:
            continue
        event_time = _time(record.get("event_time"), f"records[{index}].event_time")
        available_time = _time(record.get("available_time"), f"records[{index}].available_time")
        ingestion_time = _time(record.get("ingestion_time"), f"records[{index}].ingestion_time")
        if available_time < event_time:
            raise BaselineError(f"records[{index}].available_time precedes the bar event")
        if ingestion_time < available_time:
            raise BaselineError(f"records[{index}].ingestion_time precedes source availability")
        visible_time = available_time if as_of_mode == "source" else ingestion_time
        if event_time > cutoff or visible_time > cutoff:
            continue
        payload = record.get("payload")
        if not isinstance(payload, Mapping):
            raise BaselineError(f"records[{index}].payload must be an object")
        bar = {
            "event_time": event_time,
            "available_time": available_time,
            "ingestion_time": ingestion_time,
            "open": _decimal(payload.get("open"), f"records[{index}].open", positive=True),
            "high": _decimal(payload.get("high"), f"records[{index}].high", positive=True),
            "low": _decimal(payload.get("low"), f"records[{index}].low", positive=True),
            "close": _decimal(payload.get("close"), f"records[{index}].close", positive=True),
            "volume": _decimal(payload.get("volume"), f"records[{index}].volume"),
            "record_id": str(record.get("record_id", "")),
        }
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]):
            raise BaselineError(f"records[{index}] has inconsistent high price")
        if bar["low"] > min(bar["open"], bar["close"]):
            raise BaselineError(f"records[{index}] has inconsistent low price")
        key = event_time.isoformat()
        previous = grouped[instrument_id].get(key)
        if previous is None or (bar["available_time"], bar["ingestion_time"], bar["record_id"]) > (
            previous["available_time"],
            previous["ingestion_time"],
            previous["record_id"],
        ):
            grouped[instrument_id][key] = bar
    return {
        instrument_id: sorted(items.values(), key=lambda item: item["event_time"])
        for instrument_id, items in grouped.items()
    }


def _return(bars: list[dict[str, Any]], sessions: int) -> Decimal | None:
    if len(bars) <= sessions:
        return None
    return bars[-1]["close"] / bars[-1 - sessions]["close"] - Decimal(1)


def _positive_weights(scores: Mapping[str, Decimal]) -> dict[str, Decimal]:
    positive = {key: value for key, value in sorted(scores.items()) if value > 0}
    total = sum(positive.values(), Decimal(0))
    if total <= 0:
        return {}
    identifiers = list(positive)
    result = {key: positive[key] / total for key in identifiers[:-1]}
    result[identifiers[-1]] = Decimal(1) - sum(result.values(), Decimal(0))
    return result


def build_baseline_weights(
    name: str,
    records: Iterable[Mapping[str, Any]],
    *,
    as_of: str,
    universe_instrument_ids: Iterable[str],
    benchmark_instrument_id: str | None = None,
    lookback_sessions: int = 20,
    seed: int = 0,
    as_of_mode: str = "system",
) -> dict[str, Decimal]:
    """Build long-only reference weights using only M2-visible bars.

    An empty mapping is an explicit no-position result. Weights are targets,
    not returns or a claim that a position could have been executed.
    """
    if name not in BASELINE_NAMES:
        raise BaselineError(f"Unknown baseline {name!r}; expected one of {BASELINE_NAMES}")
    if type(lookback_sessions) is not int or lookback_sessions < 1:
        raise BaselineError("lookback_sessions must be a positive integer")
    if type(seed) is not int or seed < 0:
        raise BaselineError("seed must be a non-negative integer")
    cutoff = _time(as_of, "as_of")
    ids = list(universe_instrument_ids)
    if not ids or any(not isinstance(item, str) or not item.strip() for item in ids):
        raise BaselineError("universe_instrument_ids must contain non-empty strings")
    if len(ids) != len(set(ids)):
        raise BaselineError("universe_instrument_ids must be unique")
    grouped = _visible_records(records, set(ids), cutoff, as_of_mode)
    active = sorted(identifier for identifier, bars in grouped.items() if bars)
    if name == "equal_weight":
        if not active:
            return {}
        equal = Decimal(1) / Decimal(len(active))
        result = {identifier: equal for identifier in active[:-1]}
        result[active[-1]] = Decimal(1) - sum(result.values(), Decimal(0))
        return result
    if name == "random_control":
        if not active:
            return {}
        seed_material = f"{seed}\0{cutoff.isoformat()}".encode("utf-8")
        effective_seed = int.from_bytes(hashlib.sha256(seed_material).digest(), "big")
        generator = Random(effective_seed)
        draws = {
            identifier: Decimal(generator.getrandbits(53) + 1) / Decimal(2**53)
            for identifier in active
        }
        return _positive_weights(draws)
    if name == "benchmark":
        if benchmark_instrument_id is None:
            raise BaselineError("benchmark_instrument_id is required for the benchmark baseline")
        if benchmark_instrument_id not in ids:
            raise BaselineError("benchmark_instrument_id must belong to the declared universe")
        if benchmark_instrument_id not in grouped:
            raise BaselineError("No point-in-time price bar exists for the benchmark")
        return {benchmark_instrument_id: Decimal(1)}

    if name in {"momentum", "relative_strength", "reversal"}:
        scores: dict[str, Decimal] = {}
        benchmark_return = None
        if name == "relative_strength":
            if benchmark_instrument_id is None or benchmark_instrument_id not in grouped:
                raise BaselineError("relative_strength requires point-in-time benchmark bars")
            benchmark_return = _return(grouped[benchmark_instrument_id], lookback_sessions)
            if benchmark_return is None:
                raise BaselineError("Insufficient benchmark history for relative_strength")
        for identifier in active:
            move = _return(grouped[identifier], lookback_sessions)
            if move is None:
                continue
            if name == "momentum":
                scores[identifier] = move
            elif name == "relative_strength":
                assert benchmark_return is not None
                scores[identifier] = move - benchmark_return
            else:
                scores[identifier] = -move
        return _positive_weights(scores)

    if name == "abnormal_volume":
        scores = {}
        for identifier in active:
            bars = grouped[identifier]
            if len(bars) <= lookback_sessions:
                continue
            history = sorted(bar["volume"] for bar in bars[-1 - lookback_sessions : -1])
            middle = len(history) // 2
            typical_volume = (
                history[middle]
                if len(history) % 2
                else (history[middle - 1] + history[middle]) / Decimal(2)
            )
            if typical_volume <= 0:
                continue
            scores[identifier] = bars[-1]["volume"] / typical_volume - Decimal(1)
        return _positive_weights(scores)

    scores = {}
    for identifier in active:
        bars = grouped[identifier]
        if len(bars) <= lookback_sessions + 1:
            continue
        current = bars[-1]
        previous = bars[-1 - lookback_sessions : -1]
        previous_high = max(bar["high"] for bar in previous)
        previous_true_ranges = []
        previous_close = bars[-2 - lookback_sessions]["close"]
        for bar in previous:
            previous_true_ranges.append(
                max(bar["high"] - bar["low"], abs(bar["high"] - previous_close), abs(bar["low"] - previous_close))
            )
            previous_close = bar["close"]
        current_true_range = max(
            current["high"] - current["low"],
            abs(current["high"] - previous_close),
            abs(current["low"] - previous_close),
        )
        if current["close"] > previous_high and previous_true_ranges:
            average_range = sum(previous_true_ranges, Decimal(0)) / Decimal(len(previous_true_ranges))
            if average_range > 0 and current_true_range > average_range:
                scores[identifier] = (current["close"] / previous_high - Decimal(1)) * (
                    current_true_range / average_range
                )
    return _positive_weights(scores)


__all__ = ["BASELINE_NAMES", "BaselineError", "build_baseline_weights"]
