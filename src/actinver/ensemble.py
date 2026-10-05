"""M7 point-in-time alpha ensemble mechanics.

The module consumes only signal definitions linked to the latest verified M5
PROMOTE record. Synthetic fixtures exercise calculations but can never produce
an empirical-ready result.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from statistics import mean
from typing import Any, Mapping


class EnsembleError(ValueError):
    """Invalid promotion provenance, feature registry, or observation case."""


QUANTILES = (("q05", 0.05), ("q25", 0.25), ("q50", 0.50), ("q75", 0.75), ("q95", 0.95))
MIN_CALIBRATION_ROWS = 30
MIN_CORRELATION_ROWS = 10
HIGH_CORRELATION = 0.90


def _canonical(value: Any) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EnsembleError(f"value is not canonical JSON: {exc}") from exc


def forecast_artifact_sha256(case: Any, signal_id: str) -> str:
    """Fingerprint the case's exact raw forecast rows for one signal.

    Rows are sorted by observation_id and encoded as canonical JSON objects
    containing observation_id and forecast. M5 must record the same digest in
    its instrument_forecast_artifact before the signal can be admitted.
    """
    if type(case) is not dict or type(case.get("observations")) is not list:
        raise EnsembleError("forecast digest requires an observations array")
    selected = []
    for row in case["observations"]:
        if type(row) is not dict or type(row.get("forecasts")) is not list:
            raise EnsembleError("forecast digest encountered a malformed observation")
        for forecast in row["forecasts"]:
            if type(forecast) is dict and forecast.get("signal_id") == signal_id:
                selected.append({"observation_id": row.get("observation_id"), "forecast": forecast})
    if not selected:
        raise EnsembleError(f"forecast artifact for {signal_id!r} has no rows")
    selected.sort(key=lambda item: item["observation_id"])
    return hashlib.sha256(_canonical(selected)).hexdigest()


def _sha256(value: Any, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise EnsembleError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise EnsembleError(f"{field} must be nonempty text")
    if value != value.strip():
        raise EnsembleError(f"{field} must not contain surrounding whitespace")
    return value


def _number(value: Any, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise EnsembleError(f"{field} must be a finite number")
    result = float(value)
    if abs(result) > 1e100:
        raise EnsembleError(f"{field} is outside the supported numeric range")
    if minimum is not None and result < minimum:
        raise EnsembleError(f"{field} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise EnsembleError(f"{field} must be at most {maximum}")
    return result


def _timestamp(value: Any, field: str) -> datetime:
    if type(value) is not str:
        raise EnsembleError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnsembleError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EnsembleError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _exact_object(value: Any, required: set[str], field: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise EnsembleError(f"{field} must be an object")
    if set(value) != required:
        raise EnsembleError(
            f"{field} fields must be exactly {sorted(required)}; "
            f"missing={sorted(required - value.keys())}, unknown={sorted(value.keys() - required)}"
        )
    return dict(value)


def _promoted_map(index: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if index.get("status") != "PASS" or type(index.get("promoted_experiments")) is not list:
        raise EnsembleError("M5 promotion index is missing or invalid")
    result = {}
    for item in index["promoted_experiments"]:
        if type(item) is not dict or item.get("scientific_decision") != "PROMOTE" or item.get("m5_gate_downgraded") is not False:
            raise EnsembleError("M5 promotion index contains an ineligible decision")
        experiment_id = _text(item.get("experiment_id"), "promotion.experiment_id")
        if experiment_id in result:
            raise EnsembleError(f"duplicate promoted M5 experiment ID {experiment_id!r}")
        result[experiment_id] = item
    return result


def validate_signal_registry(registry: Any, promotions: Mapping[str, Any]) -> dict[str, Any]:
    """Validate feature definitions against exact, current M5 promotion records."""
    item = _exact_object(registry, {"schema_version", "registry_id", "signals"}, "signal registry")
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise EnsembleError("signal registry schema_version must be 1")
    _text(item["registry_id"], "signal registry.registry_id")
    if type(item["signals"]) is not list:
        raise EnsembleError("signal registry.signals must be an array")
    promoted = _promoted_map(promotions)
    normalized = []
    seen_signal_ids = set()
    seen_experiments = set()
    fields = {
        "signal_id", "experiment_id", "hypothesis_id", "promotion_record_sha256", "family_id",
        "source_type", "feature_ids", "dataset_id", "dataset_sha256", "universe_version", "target",
        "transaction_cost_model_sha256", "forecast_artifact_sha256", "horizon", "horizon_sessions",
    }
    for position, raw in enumerate(item["signals"]):
        signal = _exact_object(raw, fields, f"signal registry.signals[{position}]")
        signal_id = _text(signal["signal_id"], "signal.signal_id")
        experiment_id = _text(signal["experiment_id"], "signal.experiment_id")
        if signal_id in seen_signal_ids or experiment_id in seen_experiments:
            raise EnsembleError("signal_id and experiment_id must each be unique in the registry")
        seen_signal_ids.add(signal_id)
        seen_experiments.add(experiment_id)
        promotion = promoted.get(experiment_id)
        if promotion is None:
            raise EnsembleError(f"signal {signal_id!r} has no latest M5 PROMOTE decision")
        spec = promotion.get("experiment_spec")
        if type(spec) is not dict:
            raise EnsembleError(f"signal {signal_id!r} has no M5 ExperimentSpec")
        source_evidence = spec.get("evidence")
        if type(source_evidence) is not dict or source_evidence.get("data_status") != "authorized_point_in_time":
            raise EnsembleError(f"signal {signal_id!r} M5 evidence is not authorized point-in-time data")
        if not all(source_evidence.get(key) is True for key in (
            "source_availability_verified", "instrument_mapping_verified", "m3_execution_evidence_verified", "costs_verified",
        )):
            raise EnsembleError(f"signal {signal_id!r} M5 evidence has an unverified source, mapping, execution, or cost input")
        if source_evidence.get("final_holdout_locked") is not True or source_evidence.get("test_used_for_selection") is not False:
            raise EnsembleError(f"signal {signal_id!r} M5 evidence did not preserve an untouched final holdout")
        if source_evidence.get("m3_result_sha256") is None:
            raise EnsembleError(f"signal {signal_id!r} M5 evidence has no M3 execution result fingerprint")
        _sha256(source_evidence["m3_result_sha256"], f"{signal_id}.M5.m3_result_sha256")
        if signal["hypothesis_id"] != promotion.get("hypothesis_id"):
            raise EnsembleError(f"signal {signal_id!r} hypothesis does not match its M5 promotion")
        if _sha256(signal["promotion_record_sha256"], f"{signal_id}.promotion_record_sha256") != promotion.get("promotion_record_sha256"):
            raise EnsembleError(f"signal {signal_id!r} does not reference the current M5 promotion record")
        if signal["family_id"] != spec.get("strategy_family"):
            raise EnsembleError(f"signal {signal_id!r} family does not match its M5 ExperimentSpec")
        if type(signal["feature_ids"]) is not list or not signal["feature_ids"] or any(type(x) is not str or not x for x in signal["feature_ids"]):
            raise EnsembleError(f"signal {signal_id!r} feature_ids must be a nonempty string array")
        if signal["feature_ids"] != spec.get("features"):
            raise EnsembleError(f"signal {signal_id!r} features do not match its M5 ExperimentSpec")
        if signal["target"] != "instrument_forward_return_net_of_costs" or signal["target"] != spec.get("target"):
            raise EnsembleError(f"signal {signal_id!r} must be promoted for instrument_forward_return_net_of_costs")
        for name, expected in (
            ("dataset_id", spec.get("dataset_version")),
            ("universe_version", spec.get("universe_version")),
            ("horizon", spec.get("horizon")),
        ):
            if _text(signal[name], f"{signal_id}.{name}") != expected:
                raise EnsembleError(f"signal {signal_id!r} {name} does not match its M5 ExperimentSpec")
        manifest_sha = source_evidence.get("dataset_manifest_sha256")
        if manifest_sha is None or _sha256(manifest_sha, f"{signal_id}.M5.dataset_manifest_sha256") != signal["dataset_sha256"]:
            raise EnsembleError(f"signal {signal_id!r} dataset digest does not match its promoted M5 evidence")
        cost_model = spec.get("transaction_cost_model")
        if type(cost_model) is not dict:
            raise EnsembleError(f"signal {signal_id!r} has no M5 transaction cost model")
        cost_digest = hashlib.sha256(_canonical(cost_model)).hexdigest()
        if _sha256(signal["transaction_cost_model_sha256"], f"{signal_id}.transaction_cost_model_sha256") != cost_digest:
            raise EnsembleError(f"signal {signal_id!r} cost model digest does not match its M5 ExperimentSpec")
        validation = promotion.get("validation_result")
        artifact_fields = {
            "schema_version", "forecast_artifact_sha256", "dataset_id", "dataset_sha256", "universe_version",
            "target", "transaction_cost_model_sha256", "horizon", "horizon_sessions",
        }
        if type(validation) is not dict or type(validation.get("instrument_forecast_artifact")) is not dict:
            raise EnsembleError(f"signal {signal_id!r} M5 promotion has no per-instrument forecast artifact")
        artifact = _exact_object(validation["instrument_forecast_artifact"], artifact_fields, f"{signal_id}.M5 instrument_forecast_artifact")
        if type(artifact["schema_version"]) is not int or artifact["schema_version"] != 1 or type(artifact["horizon_sessions"]) is not int:
            raise EnsembleError(f"signal {signal_id!r} M5 forecast artifact has an unsupported version or horizon")
        artifact_expected = {
            "dataset_id": signal["dataset_id"],
            "dataset_sha256": signal["dataset_sha256"],
            "universe_version": signal["universe_version"],
            "target": signal["target"],
            "transaction_cost_model_sha256": signal["transaction_cost_model_sha256"],
            "horizon": signal["horizon"],
            "horizon_sessions": signal["horizon_sessions"],
        }
        for name, expected in artifact_expected.items():
            if artifact[name] != expected:
                raise EnsembleError(f"signal {signal_id!r} M5 forecast artifact {name} does not match the registry")
        artifact_sha = _sha256(artifact["forecast_artifact_sha256"], f"{signal_id}.M5.forecast_artifact_sha256")
        if _sha256(signal["forecast_artifact_sha256"], f"{signal_id}.forecast_artifact_sha256") != artifact_sha:
            raise EnsembleError(f"signal {signal_id!r} forecast artifact digest does not match its M5 promotion")
        if type(signal["horizon_sessions"]) is not int or signal["horizon_sessions"] < 1:
            raise EnsembleError(f"signal {signal_id!r} horizon_sessions must be a positive integer")
        if signal["source_type"] not in {"deterministic", "statistical", "quantified_event", "other_quantitative"}:
            raise EnsembleError(f"signal {signal_id!r} must have a quantitative source_type")
        signal["dataset_sha256"] = _sha256(signal["dataset_sha256"], f"{signal_id}.dataset_sha256")
        normalized.append(dict(signal))
    normalized.sort(key=lambda value: value["signal_id"])
    return {"schema_version": 1, "registry_id": item["registry_id"], "signals": normalized}


def _validate_case(
    case: Any,
    registry: Mapping[str, Any],
    *,
    instrument_ids: set[str] | None = None,
    verified_universe_version: str | None = None,
) -> dict[str, Any]:
    required = {
        "schema_version", "case_id", "dataset_id", "dataset_sha256", "universe_version", "target",
        "transaction_cost_model_sha256", "horizon", "horizon_sessions", "evidence", "observations",
    }
    item = _exact_object(case, required, "ensemble case")
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise EnsembleError("ensemble case schema_version must be 1")
    for key in ("case_id", "dataset_id", "universe_version", "target", "horizon"):
        _text(item[key], f"ensemble case.{key}")
    if item["target"] != "instrument_forward_return_net_of_costs":
        raise EnsembleError("ensemble case target must be instrument_forward_return_net_of_costs")
    item["transaction_cost_model_sha256"] = _sha256(
        item["transaction_cost_model_sha256"], "ensemble case.transaction_cost_model_sha256"
    )
    if verified_universe_version is not None and item["universe_version"] != verified_universe_version:
        raise EnsembleError("ensemble case universe_version does not match the verified M1 snapshot")
    item["dataset_sha256"] = _sha256(item["dataset_sha256"], "ensemble case.dataset_sha256")
    if type(item["horizon_sessions"]) is not int or item["horizon_sessions"] < 1:
        raise EnsembleError("ensemble case.horizon_sessions must be a positive integer")
    evidence_fields = {
        "sample_type", "source_times_verified", "instrument_mapping_verified", "execution_costs_verified",
        "final_holdout_locked", "source_manifest_sha256",
    }
    evidence = _exact_object(item["evidence"], evidence_fields, "ensemble case.evidence")
    if evidence["sample_type"] not in {"authorized_point_in_time", "synthetic_fixture"}:
        raise EnsembleError("ensemble evidence.sample_type is unsupported")
    for flag in ("source_times_verified", "instrument_mapping_verified", "execution_costs_verified", "final_holdout_locked"):
        if type(evidence[flag]) is not bool:
            raise EnsembleError(f"ensemble evidence.{flag} must be boolean")
    if evidence["source_manifest_sha256"] is not None:
        evidence["source_manifest_sha256"] = _sha256(evidence["source_manifest_sha256"], "evidence.source_manifest_sha256")
    signal_by_id = {signal["signal_id"]: signal for signal in registry["signals"]}
    for signal in registry["signals"]:
        for field, expected in (
            ("dataset_id", item["dataset_id"]),
            ("dataset_sha256", item["dataset_sha256"]),
            ("universe_version", item["universe_version"]),
            ("target", item["target"]),
            ("transaction_cost_model_sha256", item["transaction_cost_model_sha256"]),
            ("horizon", item["horizon"]),
            ("horizon_sessions", item["horizon_sessions"]),
        ):
            if signal[field] != expected:
                raise EnsembleError(f"signal {signal['signal_id']!r} {field} does not match the ensemble case")
    if evidence["sample_type"] == "authorized_point_in_time":
        if evidence["source_manifest_sha256"] is None:
            raise EnsembleError("authorized PIT data requires a source manifest fingerprint")
        if not all(evidence[key] for key in ("source_times_verified", "instrument_mapping_verified", "execution_costs_verified")):
            raise EnsembleError("authorized PIT data has unverified source, mapping, or execution evidence")
    if type(item["observations"]) is not list:
        raise EnsembleError("ensemble case.observations must be an array")
    normalized_rows = []
    observation_ids = set()
    observation_keys = set()
    row_fields = {
        "observation_id", "instrument_id", "horizon_sessions", "decision_at_utc", "target_end_at_utc",
        "split", "regime", "regime_available_at_utc", "realized_return", "forecasts",
    }
    forecast_fields = {"signal_id", "available_at_utc", "raw_score", "q05", "q25", "q50", "q75", "q95", "p_positive"}
    for position, raw in enumerate(item["observations"]):
        row = _exact_object(raw, row_fields, f"observations[{position}]")
        row_id = _text(row["observation_id"], "observation.observation_id")
        instrument = _text(row["instrument_id"], f"{row_id}.instrument_id")
        if instrument_ids is not None and instrument not in instrument_ids:
            raise EnsembleError(f"{row_id} instrument_id is absent from the verified M1 universe")
        if row_id in observation_ids:
            raise EnsembleError(f"duplicate observation_id {row_id!r}")
        observation_ids.add(row_id)
        if row["horizon_sessions"] != item["horizon_sessions"]:
            raise EnsembleError(f"{row_id} horizon_sessions does not match the case")
        decision = _timestamp(row["decision_at_utc"], f"{row_id}.decision_at_utc")
        target_end = _timestamp(row["target_end_at_utc"], f"{row_id}.target_end_at_utc")
        if target_end <= decision:
            raise EnsembleError(f"{row_id} target_end_at_utc must follow its decision time")
        if row["split"] not in {"train", "validation", "test", "live"}:
            raise EnsembleError(f"{row_id} split is unsupported")
        if row["split"] == "live":
            if row["realized_return"] is not None:
                raise EnsembleError(f"{row_id} live realized_return must be null")
        else:
            row["realized_return"] = _number(row["realized_return"], f"{row_id}.realized_return")
        if row["regime"] is not None:
            row["regime"] = _text(row["regime"], f"{row_id}.regime")
            if row["regime_available_at_utc"] is None:
                raise EnsembleError(f"{row_id} regime requires a point-in-time availability timestamp")
            if _timestamp(row["regime_available_at_utc"], f"{row_id}.regime_available_at_utc") > decision:
                raise EnsembleError(f"{row_id} regime was unavailable at decision time")
        elif row["regime_available_at_utc"] is not None:
            _timestamp(row["regime_available_at_utc"], f"{row_id}.regime_available_at_utc")
        key = (instrument, item["horizon_sessions"], decision)
        if key in observation_keys:
            raise EnsembleError(f"duplicate instrument/horizon/decision observation {key!r}")
        observation_keys.add(key)
        if type(row["forecasts"]) is not list:
            raise EnsembleError(f"{row_id}.forecasts must be an array")
        forecast_ids = set()
        forecasts = []
        for forecast_index, raw_forecast in enumerate(row["forecasts"]):
            forecast = _exact_object(raw_forecast, forecast_fields, f"{row_id}.forecasts[{forecast_index}]")
            signal_id = _text(forecast["signal_id"], f"{row_id}.forecast.signal_id")
            if signal_id not in signal_by_id:
                raise EnsembleError(f"{row_id} references unregistered signal {signal_id!r}")
            if signal_id in forecast_ids:
                raise EnsembleError(f"{row_id} contains duplicate forecast for {signal_id!r}")
            forecast_ids.add(signal_id)
            if signal_by_id[signal_id]["horizon_sessions"] != row["horizon_sessions"]:
                raise EnsembleError(f"{row_id} signal {signal_id!r} has a different horizon")
            available = _timestamp(forecast["available_at_utc"], f"{row_id}.{signal_id}.available_at_utc")
            if available > decision:
                raise EnsembleError(f"{row_id} signal {signal_id!r} was unavailable at decision time")
            clean = {
                "signal_id": signal_id,
                "available_at_utc": forecast["available_at_utc"],
                "raw_score": _number(forecast["raw_score"], f"{row_id}.{signal_id}.raw_score"),
                "p_positive": _number(forecast["p_positive"], f"{row_id}.{signal_id}.p_positive", minimum=0, maximum=1),
            }
            for name, _ in QUANTILES:
                clean[name] = _number(forecast[name], f"{row_id}.{signal_id}.{name}")
            if any(clean[left] > clean[right] for (left, _), (right, _) in zip(QUANTILES, QUANTILES[1:])):
                raise EnsembleError(f"{row_id} signal {signal_id!r} quantiles must be nondecreasing")
            forecasts.append(clean)
        row["decision_at_utc"] = decision
        row["target_end_at_utc"] = target_end
        row["forecasts"] = forecasts
        normalized_rows.append(row)
    _validate_temporal_splits(normalized_rows)
    return {**item, "observations": normalized_rows, "evidence": evidence}


def _validate_temporal_splits(rows: list[dict[str, Any]]) -> None:
    order = ("train", "validation", "test", "live")
    previous_end = None
    previous_name = None
    for split in order:
        selected = [row for row in rows if row["split"] == split]
        if not selected:
            continue
        first_decision = min(row["decision_at_utc"] for row in selected)
        last_target_end = max(row["target_end_at_utc"] for row in selected)
        if previous_end is not None and first_decision <= previous_end:
            raise EnsembleError(f"{previous_name} labels overlap or reach the {split} decision window")
        previous_end = last_target_end
        previous_name = split


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise EnsembleError("cannot compute quantile without observations")
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _robust_normalized_scores(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    groups: dict[tuple[str, int, str], list[tuple[str, float]]] = {}
    for row in rows:
        for forecast in row["forecasts"]:
            groups.setdefault((row["decision_at_utc"].isoformat(), row["horizon_sessions"], forecast["signal_id"]), []).append(
                (row["observation_id"], forecast["raw_score"])
            )
    normalized: dict[str, dict[str, float | None]] = {row["observation_id"]: {} for row in rows}
    for (_, _, signal_id), values in groups.items():
        scores = [value for _, value in values]
        if len(scores) < 3:
            for row_id, _ in values:
                normalized[row_id][signal_id] = None
            continue
        center = _quantile(scores, 0.5)
        mad = _quantile([abs(value - center) for value in scores], 0.5)
        for row_id, value in values:
            normalized[row_id][signal_id] = max(-5.0, min(5.0, (value - center) / (1.4826 * mad))) if mad else None
    return normalized


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < MIN_CORRELATION_ROWS:
        return None
    left_mean, right_mean = mean(left), mean(right)
    left_dev = [value - left_mean for value in left]
    right_dev = [value - right_mean for value in right]
    left_var = sum(value * value for value in left_dev)
    right_var = sum(value * value for value in right_dev)
    if not left_var or not right_var:
        return None
    return sum(a * b for a, b in zip(left_dev, right_dev)) / math.sqrt(left_var * right_var)


def _correlation_report(rows: list[dict[str, Any]], normalized: Mapping[str, Mapping[str, float | None]], signal_ids: list[str]) -> dict[str, Any]:
    train = [row for row in rows if row["split"] == "train"]
    matrix = {signal_id: {} for signal_id in signal_ids}
    redundant = []
    for index, left_id in enumerate(signal_ids):
        for right_id in signal_ids[index + 1 :]:
            aligned = [
                (normalized[row["observation_id"]].get(left_id), normalized[row["observation_id"]].get(right_id))
                for row in train
            ]
            pairs = [(left, right) for left, right in aligned if left is not None and right is not None]
            correlation = _pearson([pair[0] for pair in pairs], [pair[1] for pair in pairs])
            matrix[left_id][right_id] = round(correlation, 8) if correlation is not None else None
            matrix[right_id][left_id] = matrix[left_id][right_id]
            if correlation is not None and abs(correlation) >= HIGH_CORRELATION:
                redundant.append({"signal_a": left_id, "signal_b": right_id, "correlation": round(correlation, 8), "observations": len(pairs)})
    for signal_id in signal_ids:
        matrix[signal_id][signal_id] = 1.0
    return {
        "fit_split": "train",
        "minimum_pair_observations": MIN_CORRELATION_ROWS,
        "high_correlation_threshold_absolute": HIGH_CORRELATION,
        "matrix": matrix,
        "redundant_pairs": redundant,
        "selection_effect": "Diagnostics only; correlated signals are not automatically dropped or reweighted.",
    }


def _isotonic_fit(pairs: list[tuple[float, int]]) -> list[dict[str, float]] | None:
    if len(pairs) < MIN_CALIBRATION_ROWS or len({outcome for _, outcome in pairs}) < 2:
        return None
    grouped: dict[float, list[int]] = {}
    for probability, outcome in sorted(pairs):
        grouped.setdefault(probability, []).append(outcome)
    blocks = []
    for probability, outcomes in grouped.items():
        blocks.append({"min_x": probability, "max_x": probability, "sum_y": float(sum(outcomes)), "count": len(outcomes)})
        while len(blocks) >= 2:
            left, right = blocks[-2], blocks[-1]
            if left["sum_y"] / left["count"] <= right["sum_y"] / right["count"]:
                break
            blocks[-2:] = [{
                "min_x": left["min_x"], "max_x": right["max_x"],
                "sum_y": left["sum_y"] + right["sum_y"], "count": left["count"] + right["count"],
            }]
    return [
        {"min_x": block["min_x"], "max_x": block["max_x"], "rate": block["sum_y"] / block["count"]}
        for block in blocks
    ]


def _isotonic_predict(blocks: list[dict[str, float]], probability: float) -> float:
    for block in blocks:
        if probability <= block["max_x"]:
            return block["rate"]
    return blocks[-1]["rate"]


def _fit_calibrators(rows: list[dict[str, Any]], registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    train = [row for row in rows if row["split"] == "train"]
    samples: dict[tuple[str, str], list[tuple[dict[str, Any], float]]] = {}
    for row in train:
        for forecast in row["forecasts"]:
            samples.setdefault((forecast["signal_id"], row["instrument_id"]), []).append(
                (forecast, row["realized_return"])
            )
    calibrators = {}
    for (signal_id, instrument_id), values in samples.items():
        offsets = {}
        isotonic = None
        if len(values) >= MIN_CALIBRATION_ROWS:
            for name, alpha in QUANTILES:
                offsets[name] = _quantile([actual - forecast[name] for forecast, actual in values], alpha)
            isotonic = _isotonic_fit([
                (forecast["p_positive"], int(actual > 0)) for forecast, actual in values
            ])
        calibrators[(signal_id, instrument_id)] = {
            "train_observations": len(values),
            "quantile_offsets": offsets if len(values) >= MIN_CALIBRATION_ROWS else None,
            "isotonic_blocks": isotonic,
            "calibration_status": "CALIBRATED" if len(values) >= MIN_CALIBRATION_ROWS and isotonic else "INSUFFICIENT_EVIDENCE",
        }
    return calibrators


def _calibrated_forecasts(row: Mapping[str, Any], registry_by_id: Mapping[str, Mapping[str, Any]], calibrators: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for forecast in row["forecasts"]:
        signal_id = forecast["signal_id"]
        calibrator = calibrators.get((signal_id, row["instrument_id"]))
        if calibrator is None:
            continue
        blocks = calibrator["isotonic_blocks"]
        offsets = calibrator["quantile_offsets"]
        if not blocks or not offsets:
            continue
        quantiles = {name: forecast[name] + offsets[name] for name, _ in QUANTILES}
        if any(quantiles[left] > quantiles[right] for (left, _), (right, _) in zip(QUANTILES, QUANTILES[1:])):
            # Keep a forecast only when calibration preserves a valid CDF.
            continue
        result[signal_id] = {
            "family_id": registry_by_id[signal_id]["family_id"],
            "quantiles": quantiles,
            "p_positive": _isotonic_predict(blocks, forecast["p_positive"]),
        }
    return result


def _aggregate(forecasts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    if not forecasts:
        return None
    families: dict[str, list[Mapping[str, Any]]] = {}
    for forecast in forecasts.values():
        families.setdefault(forecast["family_id"], []).append(forecast)
    per_family = {
        family: {
            "quantiles": {name: mean(item["quantiles"][name] for item in members) for name, _ in QUANTILES},
            "p_positive": mean(item["p_positive"] for item in members),
        }
        for family, members in families.items()
    }
    return {
        "quantiles": {name: mean(item["quantiles"][name] for item in per_family.values()) for name, _ in QUANTILES},
        "p_positive": mean(item["p_positive"] for item in per_family.values()),
        "family_forecasts": per_family,
        "signal_count": len(forecasts),
        "family_count": len(per_family),
        "signal_ids": sorted(forecasts),
    }


def _pinball(actual: float, forecast: float, alpha: float) -> float:
    error = actual - forecast
    return max(alpha * error, (alpha - 1) * error)


def _metrics(rows: list[dict[str, Any]], predictions: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    selected = [row for row in rows if row["observation_id"] in predictions and row["realized_return"] is not None]
    if not selected:
        return {"status": "NOT_AVAILABLE", "sample_count": 0}
    absolute_errors = []
    pinballs = {name: [] for name, _ in QUANTILES}
    brier = []
    for row in selected:
        forecast = predictions[row["observation_id"]]
        actual = row["realized_return"]
        absolute_errors.append(abs(actual - forecast["quantiles"]["q50"]))
        for name, alpha in QUANTILES:
            pinballs[name].append(_pinball(actual, forecast["quantiles"][name], alpha))
        brier.append((forecast["p_positive"] - int(actual > 0)) ** 2)
    return {
        "status": "PASS" if len(selected) >= MIN_CALIBRATION_ROWS else "INSUFFICIENT_SAMPLE",
        "sample_count": len(selected),
        "median_absolute_error": round(_quantile(absolute_errors, 0.5), 10),
        "mean_pinball_loss": {name: round(mean(values), 10) for name, values in pinballs.items()},
        "brier_score_positive_return": round(mean(brier), 10),
        "probability_reliability_bins": _reliability_bins(selected, predictions),
    }


def _reliability_bins(rows: list[dict[str, Any]], predictions: Mapping[str, Mapping[str, Any]], bin_count: int = 5) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = [[] for _ in range(bin_count)]
    for row in rows:
        probability = predictions[row["observation_id"]]["p_positive"]
        index = min(bin_count - 1, int(probability * bin_count))
        groups[index].append(row)
    result = []
    for index, group in enumerate(groups):
        if not group:
            continue
        result.append({
            "lower_bound": index / bin_count,
            "upper_bound": (index + 1) / bin_count,
            "count": len(group),
            "mean_forecast_probability": round(mean(predictions[row["observation_id"]]["p_positive"] for row in group), 8),
            "observed_positive_rate": round(mean(int(row["realized_return"] > 0) for row in group), 8),
        })
    return result


def _family_independence(correlation: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    signal_family = {signal["signal_id"]: signal["family_id"] for signal in registry["signals"]}
    family_pairs: dict[tuple[str, str], list[float]] = {}
    for left_signal, row in correlation["matrix"].items():
        for right_signal, value in row.items():
            left_family, right_family = signal_family[left_signal], signal_family[right_signal]
            if left_family < right_family and value is not None:
                family_pairs.setdefault((left_family, right_family), []).append(value)
    family_corr = {pair: mean(values) for pair, values in family_pairs.items()}
    families = sorted(set(signal_family.values()))
    accepted = []
    rejected = []
    for family in families:
        if not accepted:
            accepted.append(family)
            continue
        comparisons = [
            family_corr.get(tuple(sorted((family, other))))
            for other in accepted
        ]
        if all(value is not None and abs(value) < HIGH_CORRELATION for value in comparisons):
            accepted.append(family)
        else:
            rejected.append(family)
    return {
        "family_count": len(families),
        "independent_family_count": len(accepted),
        "independent_families": accepted,
        "redundant_or_unmeasured_families": rejected,
        "pairwise_family_correlation": {" / ".join(key): round(value, 8) for key, value in sorted(family_corr.items())},
    }


def _diagnostic_forecasts(
    rows: list[dict[str, Any]], registry: Mapping[str, Any], calibrators: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id = {signal["signal_id"]: signal for signal in registry["signals"]}
    full = {}
    equal_signal = {}
    for row in rows:
        calibrated = _calibrated_forecasts(row, by_id, calibrators)
        aggregate = _aggregate(calibrated)
        if aggregate:
            full[row["observation_id"]] = aggregate
            equal_signal[row["observation_id"]] = {
                "quantiles": {name: mean(item["quantiles"][name] for item in calibrated.values()) for name, _ in QUANTILES},
                "p_positive": mean(item["p_positive"] for item in calibrated.values()),
            }
    return full, equal_signal


def evaluate_ensemble(
    registry: Any,
    case: Any,
    promotion_index: Mapping[str, Any],
    *,
    instrument_ids: set[str] | None = None,
    verified_universe_version: str | None = None,
) -> dict[str, Any]:
    """Fit calibrators on train data, aggregate promoted forecasts, and report OOS diagnostics."""
    clean_registry = validate_signal_registry(registry, promotion_index)
    clean_case = _validate_case(
        case,
        clean_registry,
        instrument_ids=instrument_ids,
        verified_universe_version=verified_universe_version,
    )
    for signal in clean_registry["signals"]:
        observed_forecast_sha = forecast_artifact_sha256(case, signal["signal_id"])
        if observed_forecast_sha != signal["forecast_artifact_sha256"]:
            raise EnsembleError(f"signal {signal['signal_id']!r} forecasts differ from the M5-promoted artifact")
    registry_sha = hashlib.sha256(_canonical(clean_registry)).hexdigest()
    case_sha = hashlib.sha256(_canonical(case)).hexdigest()
    input_trace = {
        "registry_sha256": registry_sha,
        "case_sha256": case_sha,
        "m5_ledger_head_record_sha256": promotion_index.get("ledger_head_record_sha256"),
        "verified_universe_version": verified_universe_version,
        "transaction_cost_model_sha256": case.get("transaction_cost_model_sha256"),
    }
    if not clean_registry["signals"]:
        return {
            "schema_version": 1,
            "software_status": "PASS",
            "forecast_status": "NO_PROMOTED_SIGNALS",
            "empirical_gate": "NEEDS_MORE_EVIDENCE",
            "reason": "The verified M5 promotion index contains no signals registered for instrument-level forecasting.",
            "input_trace": input_trace,
            "signal_count": 0,
            "predictions": [],
            "oos_metrics": {"validation": {"status": "NOT_AVAILABLE", "sample_count": 0}, "test": {"status": "NOT_AVAILABLE", "sample_count": 0}},
            "correlation": {"fit_split": "train", "matrix": {}, "redundant_pairs": []},
            "regime_diagnostics": [],
            "ablation": [],
            "limitations": ["No financial forecast or trade decision is produced without a current M5 PROMOTE record."],
        }

    rows = clean_case["observations"]
    signal_ids = [signal["signal_id"] for signal in clean_registry["signals"]]
    normalized = _robust_normalized_scores(rows)
    correlation = _correlation_report(rows, normalized, signal_ids)
    calibrators = _fit_calibrators(rows, clean_registry)
    calibrated_by_row, equal_signal_by_row = _diagnostic_forecasts(rows, clean_registry, calibrators)
    row_by_id = {row["observation_id"]: row for row in rows}
    test_rows = [row for row in rows if row["split"] == "test"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    test_predictions = {key: value for key, value in calibrated_by_row.items() if row_by_id[key]["split"] == "test"}
    validation_predictions = {key: value for key, value in calibrated_by_row.items() if row_by_id[key]["split"] == "validation"}
    oos_metrics = {
        "validation": _metrics(validation_rows, validation_predictions),
        "test": _metrics(test_rows, test_predictions),
        "test_equal_signal_baseline": _metrics(test_rows, equal_signal_by_row),
    }
    family_independence = _family_independence(correlation, clean_registry)
    oos_by_instrument: dict[tuple[str, int], int] = {}
    for row in test_rows:
        if row["observation_id"] in test_predictions:
            key = (row["instrument_id"], row["horizon_sessions"])
            oos_by_instrument[key] = oos_by_instrument.get(key, 0) + 1
    authorized = clean_case["evidence"]["sample_type"] == "authorized_point_in_time" and clean_case["evidence"]["final_holdout_locked"]
    registry_by_id = {signal["signal_id"]: signal for signal in clean_registry["signals"]}
    predictions = []
    for row in rows:
        if row["split"] == "train":
            continue
        aggregate = calibrated_by_row.get(row["observation_id"])
        if aggregate is None:
            predictions.append({
                "observation_id": row["observation_id"],
                "instrument_id": row["instrument_id"],
                "horizon_sessions": row["horizon_sessions"],
                "decision_at_utc": row["decision_at_utc"].isoformat().replace("+00:00", "Z"),
                "split": row["split"],
                "forecast_status": "INSUFFICIENT_CALIBRATION",
                "alpha_score": None,
                "believability_score": {"value": 0.0, "definition": "minimum of evidence-component ratios; not a probability"},
                "distribution": None,
            })
            continue
        key = (row["instrument_id"], row["horizon_sessions"])
        support = oos_by_instrument.get(key, 0)
        used_ids = aggregate["signal_ids"]
        calibration_support = min(
            calibrators[(signal_id, row["instrument_id"])]["train_observations"] / MIN_CALIBRATION_ROWS
            for signal_id in used_ids
        )
        used_families = {registry_by_id[signal_id]["family_id"] for signal_id in used_ids}
        independent_count = len(used_families.intersection(family_independence["independent_families"]))
        components = {
            "promotion_provenance": 1.0,
            "authorized_point_in_time_evidence": 1.0 if authorized else 0.0,
            "train_calibration_support": min(1.0, calibration_support),
            "instrument_horizon_oos_support": min(1.0, support / MIN_CALIBRATION_ROWS),
            "independent_family_support": min(1.0, independent_count / 2),
        }
        believability = min(components.values())
        quantiles = {name: round(aggregate["quantiles"][name], 10) for name, _ in QUANTILES}
        predictions.append({
            "observation_id": row["observation_id"],
            "instrument_id": row["instrument_id"],
            "horizon_sessions": row["horizon_sessions"],
            "decision_at_utc": row["decision_at_utc"].isoformat().replace("+00:00", "Z"),
            "split": row["split"],
            "forecast_status": "CALIBRATED_OOS_MODEL",
            "alpha_score": {
                "value": quantiles["q50"],
                "unit": "return_fraction",
                "definition": "median of the equal-family calibrated return distribution",
            },
            "believability_score": {
                "value": round(believability, 8),
                "scale": [0, 1],
                "definition": "minimum of promotion, PIT, calibration, OOS-support, and independent-family ratios; not a probability",
                "components": components,
            },
            "distribution": {
                "quantiles": quantiles,
                "probability_positive_return": round(aggregate["p_positive"], 10),
            },
            "signal_ids": used_ids,
            "family_count": aggregate["family_count"],
        })

    regime_diagnostics = []
    regimes = sorted({row["regime"] for row in test_rows if row["regime"] is not None})
    for regime in regimes:
        subset = [row for row in test_rows if row["regime"] == regime]
        predictions_for_regime = {row["observation_id"]: test_predictions[row["observation_id"]] for row in subset if row["observation_id"] in test_predictions}
        regime_diagnostics.append({"regime": regime, **_metrics(subset, predictions_for_regime)})

    ablation = []
    families = sorted({signal["family_id"] for signal in clean_registry["signals"]})
    if len(families) > 1:
        for omitted in families:
            ablated = {}
            for row in test_rows:
                full = _calibrated_forecasts(row, registry_by_id, calibrators)
                retained = {key: item for key, item in full.items() if item["family_id"] != omitted}
                aggregate = _aggregate(retained)
                if aggregate:
                    ablated[row["observation_id"]] = aggregate
            ablation.append({"omitted_family": omitted, **_metrics(test_rows, ablated)})
    else:
        ablation.append({"status": "NOT_AVAILABLE", "reason": "A family ablation requires at least two promoted families."})

    calibration_report = {
        f"{signal_id}|{instrument_id}": {
            "status": value["calibration_status"],
            "train_observations": value["train_observations"],
            "quantile_offsets": ({key: round(item, 10) for key, item in value["quantile_offsets"].items()} if value["quantile_offsets"] else None),
            "isotonic_blocks": value["isotonic_blocks"],
        }
        for (signal_id, instrument_id), value in calibrators.items()
    }
    calibrated_count = sum(value["calibration_status"] == "CALIBRATED" for value in calibrators.values())
    enough_calibration = calibrated_count > 0
    empirical_gate = "NEEDS_MORE_EVIDENCE"  # Forecast mechanics do not themselves promote an ensemble.
    return {
        "schema_version": 1,
        "software_status": "PASS",
        "forecast_status": "CALIBRATED" if enough_calibration else "INSUFFICIENT_CALIBRATION",
        "empirical_gate": empirical_gate,
        "input_trace": input_trace,
        "signal_count": len(clean_registry["signals"]),
        "calibration": {
            "fit_split": "train",
            "method": "per-signal and per-instrument empirical quantile residual correction and isotonic positive-return probability calibration",
            "minimum_train_observations_per_signal_instrument_horizon": MIN_CALIBRATION_ROWS,
            "calibrated_signal_instrument_count": calibrated_count,
            "insufficient_signal_instrument_count": len(calibrators) - calibrated_count,
            "signals": calibration_report,
        },
        "signal_normalization": {
            "method": "same-decision cross-sectional median/MAD robust z-score, clipped to [-5, 5]",
            "fit_scope": "each signal, horizon, and decision timestamp; no future rows",
            "diagnostics": normalized,
        },
        "correlation": correlation,
        "family_independence": family_independence,
        "oos_metrics": oos_metrics,
        "regime_diagnostics": regime_diagnostics,
        "ablation": ablation,
        "predictions": predictions,
        "baseline": {
            "primary": "equal-weight family means",
            "comparator": "equal-weight signal mean",
            "selection": "No weights or families selected using validation/test outcomes.",
        },
        "limitations": [
            "M5 promotion proves only its recorded experiment scope; registry matching additionally requires an instrument-level target, dataset, universe, horizon, and features.",
            "Believability is a conservative evidence score, not a probability of profit or a trade instruction.",
            "M5's hash chain is tamper-evident but is not a signed or authenticated record.",
            "A calibrated forecast does not establish positive net alpha; costs, execution, and replication gates still apply.",
        ],
    }


__all__ = ["EnsembleError", "evaluate_ensemble", "forecast_artifact_sha256", "validate_signal_registry"]
