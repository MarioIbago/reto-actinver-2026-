"""Time-aware M4 evaluation of precomputed, execution-aware portfolio returns."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from itertools import combinations
from math import e, isfinite, log, sqrt
from random import Random
from statistics import NormalDist, mean, median, stdev
from typing import Any, Mapping


class ValidationError(ValueError):
    """Raised when an M4 validation case is incomplete or inconsistent."""


_CASE_FIELDS = {
    "schema_version",
    "experiment_id",
    "hypothesis",
    "dataset_version",
    "universe_version",
    "commit_sha",
    "seed",
    "periods_per_year",
    "evidence",
    "train_period",
    "validation_period",
    "test_period",
    "bootstrap",
    "walk_forward",
    "pbo",
    "cost_sensitivity_bps",
    "benchmark_trial_id",
    "attempted_trial_count",
    "promotion_criteria",
    "trials",
}
_EVIDENCE_FIELDS = {
    "data_status",
    "source_availability_verified",
    "instrument_mapping_verified",
    "m3_execution_evidence_verified",
    "costs_verified",
    "final_holdout_locked",
    "test_used_for_selection",
    "dataset_manifest_sha256",
    "m3_result_sha256",
}
_CRITERIA_FIELDS = {
    "minimum_test_sessions",
    "minimum_test_sharpe",
    "minimum_test_cumulative_return",
    "minimum_improvement_vs_benchmark",
    "minimum_dsr_probability",
    "maximum_pbo_probability",
    "maximum_test_drawdown",
}
_UTC_SUFFIXES = ("Z", "+00:00")


def _object(value: Any, field: str, required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise ValidationError(f"{field} must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise ValidationError(f"{field} is missing fields: {', '.join(missing)}")
    if unknown:
        raise ValidationError(f"{field} has unknown fields: {', '.join(unknown)}")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be non-empty text")
    return value.strip()


def _decimal(value: Any, field: str, *, minimum: Decimal | None = None) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValidationError(f"{field} must be an exact decimal string or integer")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{field} must be a valid decimal") from exc
    if not result.is_finite() or (minimum is not None and result < minimum):
        raise ValidationError(f"{field} must be finite and at least {minimum}")
    return result


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an ISO-8601 calendar date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 calendar date") from exc


def _sha256(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValidationError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _parameters(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(key) is not str or not key.strip() for key in value):
        raise ValidationError(f"{field} must be an object with non-empty string keys")
    for key, item in value.items():
        if item is not None and type(item) not in (str, int, bool):
            raise ValidationError(f"{field}.{key} must be a string, integer, boolean, or null")
    return value


def _parameter_fingerprint(parameters: Mapping[str, Any]) -> str:
    encoded = (
        json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _periods(case: Mapping[str, Any]) -> dict[str, tuple[date, date]]:
    periods = {}
    for name in ("train_period", "validation_period", "test_period"):
        raw = _object(case[name], name, {"start", "end"})
        start = _date(raw["start"], f"{name}.start")
        end = _date(raw["end"], f"{name}.end")
        if start > end:
            raise ValidationError(f"{name}.start must not be after its end")
        periods[name] = (start, end)
    if not (
        periods["train_period"][1] < periods["validation_period"][0]
        and periods["validation_period"][1] < periods["test_period"][0]
    ):
        raise ValidationError("train, validation, and test periods must be chronological and non-overlapping")
    return periods


def _validate_case(case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, tuple[date, date]], list[date]]:
    item = _object(case, "case", _CASE_FIELDS)
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise ValidationError("schema_version must equal 1")
    for field in ("experiment_id", "hypothesis", "dataset_version", "universe_version", "benchmark_trial_id"):
        _text(item[field], field)
    if item["commit_sha"] is not None and (
        not isinstance(item["commit_sha"], str)
        or len(item["commit_sha"]) != 40
        or any(character not in "0123456789abcdef" for character in item["commit_sha"])
    ):
        raise ValidationError("commit_sha must be null or a full lowercase Git SHA")
    if type(item["seed"]) is not int or item["seed"] < 0:
        raise ValidationError("seed must be a non-negative integer")
    if type(item["periods_per_year"]) is not int or not 1 <= item["periods_per_year"] <= 10000:
        raise ValidationError("periods_per_year must be a positive integer")

    evidence = _object(item["evidence"], "evidence", _EVIDENCE_FIELDS)
    if evidence["data_status"] not in {"synthetic_fixture", "authorized_point_in_time", "unverified"}:
        raise ValidationError("evidence.data_status is unsupported")
    for field in (
        "source_availability_verified",
        "instrument_mapping_verified",
        "m3_execution_evidence_verified",
        "costs_verified",
        "final_holdout_locked",
        "test_used_for_selection",
    ):
        if type(evidence[field]) is not bool:
            raise ValidationError(f"evidence.{field} must be boolean")
    _sha256(evidence["dataset_manifest_sha256"], "evidence.dataset_manifest_sha256", nullable=True)
    _sha256(evidence["m3_result_sha256"], "evidence.m3_result_sha256", nullable=True)
    periods = _periods(item)

    bootstrap = _object(item["bootstrap"], "bootstrap", {"iterations", "block_length", "confidence_level"})
    if type(bootstrap["iterations"]) is not int or not 100 <= bootstrap["iterations"] <= 10000:
        raise ValidationError("bootstrap.iterations must be between 100 and 10000")
    if type(bootstrap["block_length"]) is not int or bootstrap["block_length"] < 1:
        raise ValidationError("bootstrap.block_length must be a positive integer")
    confidence = _decimal(bootstrap["confidence_level"], "bootstrap.confidence_level")
    if not Decimal(0) < confidence < Decimal(1):
        raise ValidationError("bootstrap.confidence_level must be in (0, 1)")

    walk = _object(
        item["walk_forward"],
        "walk_forward",
        {"mode", "train_sessions", "evaluation_sessions", "step_sessions"},
    )
    if walk["mode"] not in {"expanding", "rolling"}:
        raise ValidationError("walk_forward.mode must be expanding or rolling")
    for field in ("train_sessions", "evaluation_sessions", "step_sessions"):
        if type(walk[field]) is not int or walk[field] < 1:
            raise ValidationError(f"walk_forward.{field} must be a positive integer")
    if walk["step_sessions"] != walk["evaluation_sessions"]:
        raise ValidationError("walk_forward.step_sessions must equal evaluation_sessions to avoid overlapping OOS folds")

    pbo = _object(item["pbo"], "pbo", {"blocks"})
    if type(pbo["blocks"]) is not int or pbo["blocks"] < 4 or pbo["blocks"] > 12 or pbo["blocks"] % 2:
        raise ValidationError("pbo.blocks must be an even integer between 4 and 12")
    cost_sensitivity = item["cost_sensitivity_bps"]
    if not isinstance(cost_sensitivity, list) or not cost_sensitivity:
        raise ValidationError("cost_sensitivity_bps must be a non-empty array")
    parsed_costs = [_decimal(value, "cost_sensitivity_bps item", minimum=Decimal(0)) for value in cost_sensitivity]
    if len(set(parsed_costs)) != len(parsed_costs):
        raise ValidationError("cost_sensitivity_bps values must be unique")

    attempted = item["attempted_trial_count"]
    if type(attempted) is not int or not 1 <= attempted <= 1000000:
        raise ValidationError("attempted_trial_count must be between 1 and 1000000")
    criteria = _object(item["promotion_criteria"], "promotion_criteria", _CRITERIA_FIELDS)
    if type(criteria["minimum_test_sessions"]) is not int or criteria["minimum_test_sessions"] < 1:
        raise ValidationError("promotion_criteria.minimum_test_sessions must be a positive integer")
    for field in _CRITERIA_FIELDS - {"minimum_test_sessions"}:
        value = _decimal(criteria[field], f"promotion_criteria.{field}")
        if field in {"minimum_dsr_probability", "maximum_pbo_probability", "maximum_test_drawdown"} and not Decimal(0) <= value <= Decimal(1):
            raise ValidationError(f"promotion_criteria.{field} must be in [0, 1]")

    raw_trials = item["trials"]
    if not isinstance(raw_trials, list) or len(raw_trials) < 2:
        raise ValidationError("trials must contain at least two reference candidates")
    if attempted < len(raw_trials):
        raise ValidationError("attempted_trial_count cannot be smaller than the listed trial count")
    trial_ids = set()
    shared_dates: list[date] | None = None
    for trial_index, raw_trial in enumerate(raw_trials):
        trial = _object(
            raw_trial,
            f"trials[{trial_index}]",
            {"trial_id", "parameters", "parameter_sha256", "returns"},
        )
        trial_id = _text(trial["trial_id"], f"trials[{trial_index}].trial_id")
        if trial_id in trial_ids:
            raise ValidationError(f"Duplicate trial_id {trial_id}")
        trial_ids.add(trial_id)
        parameters = _parameters(trial["parameters"], f"trials[{trial_index}].parameters")
        parameter_sha = _sha256(trial["parameter_sha256"], f"trials[{trial_index}].parameter_sha256")
        if parameter_sha != _parameter_fingerprint(parameters):
            raise ValidationError(f"trials[{trial_index}].parameter_sha256 does not match its parameters")
        rows = trial["returns"]
        if not isinstance(rows, list):
            raise ValidationError(f"trials[{trial_index}].returns must be an array")
        dates = []
        for row_index, raw_row in enumerate(rows):
            row = _object(raw_row, f"trials[{trial_index}].returns[{row_index}]", {"date", "gross_return", "turnover", "regime"})
            period_date = _date(row["date"], f"trials[{trial_index}].returns[{row_index}].date")
            gross_return = _decimal(row["gross_return"], "gross_return", minimum=Decimal(-1))
            if gross_return < Decimal(-1):
                raise ValidationError("gross_return cannot be less than -1")
            _decimal(row["turnover"], "turnover", minimum=Decimal(0))
            if row["regime"] is not None:
                _text(row["regime"], "regime")
            dates.append(period_date)
        if dates != sorted(set(dates)):
            raise ValidationError(f"trials[{trial_index}].returns dates must be strictly increasing")
        if shared_dates is None:
            shared_dates = dates
        elif dates != shared_dates:
            raise ValidationError("all trials must have identical, aligned return dates")
    if item["benchmark_trial_id"] not in trial_ids:
        raise ValidationError("benchmark_trial_id must name one of the listed trials")
    assert shared_dates is not None
    first_period = periods["train_period"][0]
    last_period = periods["test_period"][1]
    if not shared_dates or shared_dates[0] < first_period or shared_dates[-1] > last_period:
        raise ValidationError("trial returns must lie within the declared train-through-test period")
    return item, periods, shared_dates


def _metric_summary(
    returns: list[float],
    turnovers: list[float],
    cost_drags: list[float],
    periods_per_year: int,
) -> dict[str, Any]:
    if not returns:
        return {
            "period_count": 0,
            "mean_period_return": None,
            "annualized_volatility": None,
            "annualized_sharpe": None,
            "cumulative_return": None,
            "maximum_drawdown": None,
            "hit_rate": None,
            "total_turnover": 0.0,
            "total_cost_drag": 0.0,
        }
    avg = mean(returns)
    volatility = stdev(returns) if len(returns) > 1 else None
    sharpe = avg / volatility * sqrt(periods_per_year) if volatility and volatility > 0 else None
    wealth = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        wealth *= 1 + value
        peak = max(peak, wealth)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - wealth) / peak)
    result = {
        "period_count": len(returns),
        "mean_period_return": avg,
        "annualized_volatility": volatility * sqrt(periods_per_year) if volatility is not None else None,
        "annualized_sharpe": sharpe,
        "cumulative_return": wealth - 1,
        "maximum_drawdown": max_drawdown,
        "hit_rate": sum(value > 0 for value in returns) / len(returns),
        "total_turnover": sum(turnovers),
        "total_cost_drag": sum(cost_drags),
    }
    return {key: _finite_round(value) if isinstance(value, float) else value for key, value in result.items()}


def _finite_round(value: float) -> float | None:
    if not isfinite(value):
        return None
    return round(value, 12)


def _rows_for_period(trial: Mapping[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    return [row for row in trial["returns"] if start <= date.fromisoformat(row["date"]) <= end]


def _net_values(
    rows: list[Mapping[str, Any]],
    *,
    fee_rate: Decimal,
    slippage_bps: Decimal,
) -> tuple[list[float], list[float], list[float]]:
    per_side_cost = fee_rate + slippage_bps / Decimal(10000)
    returns = []
    turnover = []
    cost_drag = []
    for row in rows:
        gross = _decimal(row["gross_return"], "gross_return", minimum=Decimal(-1))
        traded = _decimal(row["turnover"], "turnover", minimum=Decimal(0))
        drag = traded * per_side_cost
        returns.append(float(gross - drag))
        turnover.append(float(traded))
        cost_drag.append(float(drag))
    return returns, turnover, cost_drag


def _slice_metrics(
    trial: Mapping[str, Any],
    start: date,
    end: date,
    *,
    fee_rate: Decimal,
    slippage_bps: Decimal,
    periods_per_year: int,
) -> tuple[list[dict[str, Any]], list[float], dict[str, Any]]:
    rows = _rows_for_period(trial, start, end)
    values, turnovers, costs = _net_values(rows, fee_rate=fee_rate, slippage_bps=slippage_bps)
    return rows, values, _metric_summary(values, turnovers, costs, periods_per_year)


def _mean_sharpe(values: list[float]) -> float:
    if len(values) < 2:
        return float("-inf")
    volatility = stdev(values)
    if volatility == 0:
        return float("inf") if mean(values) > 0 else float("-inf") if mean(values) < 0 else 0.0
    return mean(values) / volatility


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    position = 1
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average_rank = (position + position + (end - cursor) - 1) / 2
        for offset in range(cursor, end):
            ranks[order[offset]] = average_rank
        position += end - cursor
        cursor = end
    return ranks


def _pbo(
    trial_values: list[list[float]],
    *,
    blocks: int,
) -> dict[str, Any]:
    n_trials = len(trial_values)
    n_periods = len(trial_values[0]) if trial_values else 0
    if n_trials < 2:
        return {"status": "NOT_APPLICABLE", "reason": "fewer than two trials"}
    if n_periods < blocks:
        return {"status": "NOT_APPLICABLE", "reason": "fewer observations than requested CSCV blocks"}
    sizes = [n_periods // blocks + (1 if index < n_periods % blocks else 0) for index in range(blocks)]
    block_indices: list[list[int]] = []
    cursor = 0
    for size in sizes:
        block_indices.append(list(range(cursor, cursor + size)))
        cursor += size
    half = blocks // 2
    total_splits = 0
    overfit = 0
    logits = []
    for chosen in combinations(range(blocks), half):
        in_blocks = set(chosen)
        in_indices = [index for block_index in chosen for index in block_indices[block_index]]
        out_indices = [index for block_index in range(blocks) if block_index not in in_blocks for index in block_indices[block_index]]
        in_scores = [_mean_sharpe([trial[index] for index in in_indices]) for trial in trial_values]
        winner = max(range(n_trials), key=lambda index: (in_scores[index], -index))
        out_scores = [_mean_sharpe([trial[index] for index in out_indices]) for trial in trial_values]
        ranks = _average_ranks(out_scores)
        omega = ranks[winner] / (n_trials + 1)
        if 0 < omega < 1:
            logits.append(log(omega / (1 - omega)))
            overfit += omega < 0.5
        total_splits += 1
    return {
        "status": "PASS",
        "method": "CSCV",
        "blocks": blocks,
        "trial_count": n_trials,
        "split_count": total_splits,
        "probability_backtest_overfit": overfit / total_splits if total_splits else None,
        "median_oos_rank_logit": median(logits) if logits else None,
        "selection_uses_final_test": False,
        "rank_convention": "average rank ascending from worst to best; PBO counts selected OOS rank below median",
    }


def _dsr(
    validation_values: list[list[float]],
    selected_index: int,
    attempted_trials: int,
) -> dict[str, Any]:
    if attempted_trials < 2 or len(validation_values) < 2:
        return {"status": "NOT_APPLICABLE", "reason": "at least two tried variants are required"}
    selected = validation_values[selected_index]
    n = len(selected)
    if n < 3:
        return {"status": "NOT_APPLICABLE", "reason": "at least three validation observations are required"}
    selected_sharpe = _mean_sharpe(selected)
    if not isfinite(selected_sharpe):
        return {"status": "NOT_APPLICABLE", "reason": "selected validation Sharpe is undefined"}
    trial_sharpes = [_mean_sharpe(values) for values in validation_values]
    finite_sharpes = [value for value in trial_sharpes if isfinite(value)]
    if len(finite_sharpes) < 2:
        return {"status": "NOT_APPLICABLE", "reason": "fewer than two finite trial Sharpes"}
    sharpe_dispersion = stdev(finite_sharpes)
    if sharpe_dispersion == 0:
        selection_threshold = mean(finite_sharpes)
    else:
        normal = NormalDist()
        gamma = 0.5772156649015329
        z1 = normal.inv_cdf(1 - 1 / attempted_trials)
        z2 = normal.inv_cdf(1 - 1 / (attempted_trials * e))
        selection_threshold = mean(finite_sharpes) + sharpe_dispersion * ((1 - gamma) * z1 + gamma * z2)
    average = mean(selected)
    variance = sum((value - average) ** 2 for value in selected) / n
    if variance == 0:
        return {"status": "NOT_APPLICABLE", "reason": "selected validation variance is zero"}
    skew = sum((value - average) ** 3 for value in selected) / n / (variance**1.5)
    excess_kurtosis = sum((value - average) ** 4 for value in selected) / n / (variance**2) - 3
    variance_factor = 1 - skew * selected_sharpe + ((excess_kurtosis + 2) / 4) * selected_sharpe**2
    if variance_factor <= 0:
        return {"status": "NOT_APPLICABLE", "reason": "non-normality correction is not positive"}
    z_score = (selected_sharpe - selection_threshold) * sqrt(n - 1) / sqrt(variance_factor)
    probability = NormalDist().cdf(z_score)
    return {
        "status": "PASS",
        "selected_validation_sharpe_per_period": _finite_round(selected_sharpe),
        "expected_max_sharpe_threshold_per_period": _finite_round(selection_threshold),
        "attempted_trial_count": attempted_trials,
        "observations": n,
        "skewness": _finite_round(skew),
        "excess_kurtosis": _finite_round(excess_kurtosis),
        "deflated_sharpe_probability": _finite_round(probability),
        "annualization_applied_to_probability": False,
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    location = probability * (len(ordered) - 1)
    low = int(location)
    high = min(low + 1, len(ordered) - 1)
    weight = location - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _block_bootstrap(
    values: list[float],
    *,
    iterations: int,
    block_length: int,
    confidence: float,
    seed: int,
) -> dict[str, Any]:
    if len(values) < 2:
        return {"status": "NOT_APPLICABLE", "reason": "fewer than two observations"}
    generator = Random(seed)
    bootstrap_means = []
    n = len(values)
    for _ in range(iterations):
        sample = []
        while len(sample) < n:
            start = generator.randrange(n)
            sample.extend(values[(start + offset) % n] for offset in range(block_length))
        bootstrap_means.append(mean(sample[:n]))
    tail = (1 - confidence) / 2
    return {
        "status": "PASS",
        "method": "circular_moving_block_percentile",
        "iterations": iterations,
        "block_length": block_length,
        "confidence_level": confidence,
        "mean_return_point_estimate": _finite_round(mean(values)),
        "mean_return_interval": [
            _finite_round(_percentile(bootstrap_means, tail)),
            _finite_round(_percentile(bootstrap_means, 1 - tail)),
        ],
        "seed": seed,
    }


def _walk_forward(
    trials: list[Mapping[str, Any]],
    dates: list[date],
    *,
    config: Mapping[str, Any],
    test_start: date,
    fee_rate: Decimal,
    periods_per_year: int,
) -> dict[str, Any]:
    available_dates = [item for item in dates if item < test_start]
    train_sessions = config["train_sessions"]
    evaluation_sessions = config["evaluation_sessions"]
    step = config["step_sessions"]
    folds = []
    combined_returns: list[float] = []
    for evaluation_start in range(train_sessions, len(available_dates) - evaluation_sessions + 1, step):
        if config["mode"] == "expanding":
            train_start = 0
        else:
            train_start = evaluation_start - train_sessions
        train_dates = set(available_dates[train_start:evaluation_start])
        evaluation_dates = available_dates[evaluation_start : evaluation_start + evaluation_sessions]
        train_scores = []
        for trial in trials:
            rows = [row for row in trial["returns"] if date.fromisoformat(row["date"]) in train_dates]
            values, _, _ = _net_values(rows, fee_rate=fee_rate, slippage_bps=Decimal(0))
            train_scores.append(_mean_sharpe(values))
        selected_index = max(range(len(trials)), key=lambda index: (train_scores[index], -index))
        selected = trials[selected_index]
        selected_rows = [row for row in selected["returns"] if date.fromisoformat(row["date"]) in set(evaluation_dates)]
        values, turnovers, costs = _net_values(selected_rows, fee_rate=fee_rate, slippage_bps=Decimal(0))
        combined_returns.extend(values)
        folds.append(
            {
                "train_start": available_dates[train_start].isoformat(),
                "train_end": available_dates[evaluation_start - 1].isoformat(),
                "evaluation_start": evaluation_dates[0].isoformat(),
                "evaluation_end": evaluation_dates[-1].isoformat(),
                "selected_trial_id": selected["trial_id"],
                "evaluation_metrics": _metric_summary(values, turnovers, costs, periods_per_year),
            }
        )
    if not folds:
        return {
            "status": "NOT_APPLICABLE",
            "reason": "not enough pre-holdout observations for the requested folds",
            "mode": config["mode"],
            "folds": [],
        }
    return {
        "status": "PASS",
        "mode": config["mode"],
        "fold_count": len(folds),
        "folds": folds,
        "aggregate_oos_metrics": _metric_summary(
            combined_returns,
            [0.0] * len(combined_returns),
            [0.0] * len(combined_returns),
            periods_per_year,
        ),
        "final_test_period_used": False,
    }


def _regime_metrics(rows: list[Mapping[str, Any]], *, fee_rate: Decimal, periods_per_year: int) -> dict[str, Any]:
    buckets: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if row["regime"] is None:
            continue
        buckets.setdefault(row["regime"], []).append(row)
    if not buckets:
        return {"status": "NOT_AVAILABLE", "groups": {}}
    result = {}
    for name, group in sorted(buckets.items()):
        values, turnovers, costs = _net_values(group, fee_rate=fee_rate, slippage_bps=Decimal(0))
        result[name] = _metric_summary(values, turnovers, costs, periods_per_year)
    return {"status": "PASS", "groups": result}


def _parameter_sensitivity(
    trials: list[Mapping[str, Any]],
    trial_reports: Mapping[str, Any],
) -> dict[str, Any]:
    values_by_parameter: dict[str, dict[str, list[float]]] = {}
    for trial in trials:
        score = trial_reports[trial["trial_id"]]["validation_metrics"]["annualized_sharpe"]
        if score is None:
            continue
        for name, value in trial["parameters"].items():
            value_key = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            values_by_parameter.setdefault(name, {}).setdefault(value_key, []).append(score)
    summary = {}
    for name, value_groups in sorted(values_by_parameter.items()):
        groups = {
            value_key: {
                "trial_count": len(scores),
                "mean_validation_annualized_sharpe": _finite_round(mean(scores)),
            }
            for value_key, scores in sorted(value_groups.items())
        }
        means = [item["mean_validation_annualized_sharpe"] for item in groups.values()]
        if len(groups) > 1 and all(value is not None for value in means):
            spread = max(means) - min(means)
        else:
            spread = None
        summary[name] = {
            "value_groups": groups,
            "validation_sharpe_range": _finite_round(spread) if spread is not None else None,
        }
    return {
        "status": "PASS" if summary else "NOT_AVAILABLE",
        "parameters": summary,
        "interpretation": "Descriptive sensitivity across submitted variants; correlated changes are not causal attribution.",
    }


def evaluate_validation_case(
    case: Mapping[str, Any],
    ruleset: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate aligned gross portfolio returns without selecting on the final holdout.

    The input returns must be periodic portfolio returns before the versioned
    Actinver fee and before the supplied per-side slippage sensitivity. Their
    positions and trade quantities must already come from an M3 replay or an
    explicitly named equivalent. This function does not generate fills.
    """
    item, periods, dates = _validate_case(case)
    commissions = Decimal(str(ruleset["rules"]["costs"]["commission_rate"]))
    iva = Decimal(str(ruleset["rules"]["costs"]["iva_rate_on_commission"]))
    fee_rate = commissions * (Decimal(1) + iva)
    trials = item["trials"]
    trial_by_id = {trial["trial_id"]: trial for trial in trials}
    trial_ids = sorted(trial_by_id)
    ordered_trials = [trial_by_id[identifier] for identifier in trial_ids]
    selected_slippage = Decimal(0)
    train_range = periods["train_period"]
    validation_range = periods["validation_period"]
    test_range = periods["test_period"]
    train_validation = [
        period_date
        for period_date in dates
        if train_range[0] <= period_date <= train_range[1]
        or validation_range[0] <= period_date <= validation_range[1]
    ]

    trial_reports = {}
    validation_values = []
    for trial in ordered_trials:
        _train_rows, _train_values, train_metrics = _slice_metrics(
            trial,
            *train_range,
            fee_rate=fee_rate,
            slippage_bps=selected_slippage,
            periods_per_year=item["periods_per_year"],
        )
        _validation_rows, validation_net, validation_metrics = _slice_metrics(
            trial,
            *validation_range,
            fee_rate=fee_rate,
            slippage_bps=selected_slippage,
            periods_per_year=item["periods_per_year"],
        )
        validation_values.append(validation_net)
        trial_reports[trial["trial_id"]] = {
            "parameter_sha256": trial["parameter_sha256"],
            "train_metrics": train_metrics,
            "validation_metrics": validation_metrics,
        }
    selected_index = max(
        range(len(ordered_trials)),
        key=lambda index: (
            _mean_sharpe(validation_values[index]),
            -index,
        ),
    )
    selected = ordered_trials[selected_index]
    benchmark = trial_by_id[item["benchmark_trial_id"]]
    test_rows, test_values, test_metrics = _slice_metrics(
        selected,
        *test_range,
        fee_rate=fee_rate,
        slippage_bps=selected_slippage,
        periods_per_year=item["periods_per_year"],
    )
    _bench_rows, _bench_values, benchmark_test_metrics = _slice_metrics(
        benchmark,
        *test_range,
        fee_rate=fee_rate,
        slippage_bps=selected_slippage,
        periods_per_year=item["periods_per_year"],
    )
    test_improvement = None
    if test_metrics["cumulative_return"] is not None and benchmark_test_metrics["cumulative_return"] is not None:
        test_improvement = _finite_round(
            test_metrics["cumulative_return"] - benchmark_test_metrics["cumulative_return"]
        )

    validation_net_by_trial = [validation_values[index] for index in range(len(ordered_trials))]
    pbo_rows = []
    for trial in ordered_trials:
        rows = [row for row in trial["returns"] if date.fromisoformat(row["date"]) in set(train_validation)]
        net, _, _ = _net_values(rows, fee_rate=fee_rate, slippage_bps=Decimal(0))
        pbo_rows.append(net)
    pbo_result = _pbo(pbo_rows, blocks=item["pbo"]["blocks"])
    dsr_result = _dsr(
        validation_net_by_trial,
        selected_index,
        item["attempted_trial_count"],
    )
    wf_result = _walk_forward(
        ordered_trials,
        dates,
        config=item["walk_forward"],
        test_start=test_range[0],
        fee_rate=fee_rate,
        periods_per_year=item["periods_per_year"],
    )
    bootstrap_result = _block_bootstrap(
        test_values,
        iterations=item["bootstrap"]["iterations"],
        block_length=item["bootstrap"]["block_length"],
        confidence=float(_decimal(item["bootstrap"]["confidence_level"], "confidence_level")),
        seed=item["seed"],
    )
    cost_sensitivity = []
    for raw_bps in item["cost_sensitivity_bps"]:
        bps = _decimal(raw_bps, "cost_sensitivity_bps item", minimum=Decimal(0))
        _, _, validation_metrics = _slice_metrics(
            selected,
            *validation_range,
            fee_rate=fee_rate,
            slippage_bps=bps,
            periods_per_year=item["periods_per_year"],
        )
        _, _, cost_test_metrics = _slice_metrics(
            selected,
            *test_range,
            fee_rate=fee_rate,
            slippage_bps=bps,
            periods_per_year=item["periods_per_year"],
        )
        cost_sensitivity.append(
            {
                "slippage_bps_per_side": str(bps),
                "validation_metrics": validation_metrics,
                "test_metrics": cost_test_metrics,
            }
        )

    groups = _regime_metrics(test_rows, fee_rate=fee_rate, periods_per_year=item["periods_per_year"])
    criteria = item["promotion_criteria"]
    criteria_failures = []
    evidence_gaps = []
    minimum_test_sessions = criteria["minimum_test_sessions"]
    if test_metrics["period_count"] < minimum_test_sessions:
        evidence_gaps.append(
            f"test sample has {test_metrics['period_count']} observations; {minimum_test_sessions} required"
        )
    else:
        if test_metrics["annualized_sharpe"] is None or test_metrics["annualized_sharpe"] < float(criteria["minimum_test_sharpe"]):
            criteria_failures.append("test annualized Sharpe is below the preregistered minimum")
        if test_metrics["cumulative_return"] is None or test_metrics["cumulative_return"] < float(criteria["minimum_test_cumulative_return"]):
            criteria_failures.append("test cumulative return is below the preregistered minimum")
        if test_improvement is None or test_improvement < float(criteria["minimum_improvement_vs_benchmark"]):
            criteria_failures.append("test improvement over the named benchmark is below the preregistered minimum")
        if test_metrics["maximum_drawdown"] is None or test_metrics["maximum_drawdown"] > float(criteria["maximum_test_drawdown"]):
            criteria_failures.append("test maximum drawdown exceeds the preregistered maximum")
    if dsr_result["status"] != "PASS":
        evidence_gaps.append(f"Deflated Sharpe Ratio unavailable: {dsr_result.get('reason', 'unknown reason')}")
    elif dsr_result["deflated_sharpe_probability"] < float(criteria["minimum_dsr_probability"]):
        criteria_failures.append("Deflated Sharpe probability is below the preregistered minimum")
    if pbo_result["status"] != "PASS":
        evidence_gaps.append(f"PBO unavailable: {pbo_result.get('reason', 'unknown reason')}")
    elif pbo_result["probability_backtest_overfit"] > float(criteria["maximum_pbo_probability"]):
        criteria_failures.append("PBO exceeds the preregistered maximum")

    evidence = item["evidence"]
    if evidence["test_used_for_selection"]:
        criteria_failures.append("final holdout was used for trial selection")
    if not evidence["final_holdout_locked"]:
        evidence_gaps.append("final holdout lock is not attested")
    if evidence["data_status"] != "authorized_point_in_time":
        evidence_gaps.append("data is not identified as an authorized point-in-time dataset")
    for field, label in (
        ("source_availability_verified", "source availability times are not verified"),
        ("instrument_mapping_verified", "instrument mapping is not verified"),
        ("m3_execution_evidence_verified", "M3 execution evidence is not verified"),
        ("costs_verified", "transaction-cost inputs are not verified"),
    ):
        if not evidence[field]:
            evidence_gaps.append(label)
    if evidence["dataset_manifest_sha256"] is None:
        evidence_gaps.append("dataset manifest fingerprint is missing")
    if evidence["m3_result_sha256"] is None:
        evidence_gaps.append("M3 result fingerprint is missing")

    if criteria_failures:
        promotion_status = "REJECT"
        reasons = criteria_failures
    elif evidence_gaps:
        promotion_status = "NEEDS_MORE_EVIDENCE"
        reasons = evidence_gaps
    else:
        promotion_status = "PROMOTE"
        reasons = ["all preregistered criteria and supplied provenance assertions passed"]

    return {
        "schema_version": 1,
        "status": "PASS",
        "experiment_id": item["experiment_id"],
        "hypothesis": item["hypothesis"],
        "dataset_version": item["dataset_version"],
        "universe_version": item["universe_version"],
        "status_decision": promotion_status,
        "decision_reasons": reasons,
        "selected_trial_id": selected["trial_id"],
        "benchmark_trial_id": benchmark["trial_id"],
        "metrics": {
            "selection_metric": "validation_annualized_sharpe",
            "selected_trial": {
                "train": trial_reports[selected["trial_id"]]["train_metrics"],
                "validation": trial_reports[selected["trial_id"]]["validation_metrics"],
                "test": test_metrics,
            },
            "benchmark_test": benchmark_test_metrics,
            "test_improvement_vs_benchmark": test_improvement,
            "trial_selection_metrics": trial_reports,
        },
        "cost_model": {
            "commission_rate": str(commissions),
            "iva_rate_on_commission": str(iva),
            "combined_fee_rate_per_side": str(fee_rate),
            "risk_free_rate": "0",
            "turnover_definition": "total absolute traded notional divided by prior portfolio value",
        },
        "cost_sensitivity": cost_sensitivity,
        "parameter_sensitivity": _parameter_sensitivity(ordered_trials, trial_reports),
        "walk_forward": wf_result,
        "bootstrap": bootstrap_result,
        "pbo": pbo_result,
        "deflated_sharpe_ratio": dsr_result,
        "regime_splits": groups,
        "sample_size_diagnostics": {
            "train_sessions": trial_reports[selected["trial_id"]]["train_metrics"]["period_count"],
            "validation_sessions": trial_reports[selected["trial_id"]]["validation_metrics"]["period_count"],
            "test_sessions": test_metrics["period_count"],
            "test_minimum_sessions": minimum_test_sessions,
            "small_test_sample": test_metrics["period_count"] < 30,
        },
        "multiple_testing_context": {
            "attempted_trial_count": item["attempted_trial_count"],
            "reported_trial_count": len(ordered_trials),
            "selection_period": "validation",
            "final_test_used_for_selection": evidence["test_used_for_selection"],
            "parameter_hashes": {trial["trial_id"]: trial["parameter_sha256"] for trial in ordered_trials},
        },
        "leakage_checks": {
            "chronological_non_overlapping_splits": True,
            "trial_return_dates_aligned": True,
            "selected_on_validation_only": not evidence["test_used_for_selection"],
            "walk_forward_excludes_final_test": wf_result.get("final_test_period_used") is False,
            "final_holdout_lock_attested": evidence["final_holdout_locked"],
            "limitations": [
                "The evaluator receives portfolio returns and turnover; it does not independently reconstruct M3 fills or source-data availability.",
                "Provenance flags and SHA-256 values are caller-supplied assertions, not cryptographic validation of an external manifest or M3 result.",
                "Bootstrap, PBO, and DSR assumptions are approximate diagnostics and do not establish that an edge is real.",
            ],
        },
        "evidence_status": evidence["data_status"],
        "evidence_gaps": evidence_gaps,
    }


__all__ = ["ValidationError", "evaluate_validation_case"]
