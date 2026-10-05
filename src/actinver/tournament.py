"""M8 deterministic scenario comparison for rank-aware portfolio decisions.

This module compares feasible target portfolios on joint, net-of-cost scenario
banks. It is deliberately a simulation interface, not an order generator.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import math
import random
import re
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from .m1 import eligible_instruments, validate_portfolio


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EQUITY_CATEGORIES = {"national_equity", "sic_equity"}
POSITION_CAP_TOLERANCE = 1e-10


class TournamentError(ValueError):
    """Raised when M8 inputs cannot support a reproducible comparison."""


def _canonical(value: Any) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TournamentError(f"value cannot be represented as canonical JSON: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _fields(value: Any, required: set[str], optional: set[str], name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise TournamentError(f"{name} must be an object")
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise TournamentError(f"{name} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise TournamentError(f"{name} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise TournamentError(f"{name} must be a non-empty string")
    return value.strip()


def _number(value: Any, name: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise TournamentError(f"{name} must be a finite JSON number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise TournamentError(f"{name} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise TournamentError(f"{name} must be at most {maximum}")
    return result


def _integer(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        suffix = f" and at most {maximum}" if maximum is not None else ""
        raise TournamentError(f"{name} must be an integer at least {minimum}{suffix}")
    return value


def _sha(value: Any, name: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if type(value) is not str or not SHA256_RE.fullmatch(value):
        raise TournamentError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _instant(value: Any, name: str) -> datetime:
    if type(value) is not str:
        raise TournamentError(f"{name} must be an ISO-8601 timestamp with a UTC offset")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise TournamentError(f"{name} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TournamentError(f"{name} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _weighted_quantile(values: Sequence[tuple[float, float]], quantile: float) -> float:
    ordered = sorted(values)
    total = sum(weight for _value, weight in ordered)
    if not ordered or total <= 0:
        return 0.0
    cutoff = quantile * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative + 1e-15 >= cutoff:
            return value
    return ordered[-1][0]


def _scenario_rows(value: Any, name: str, competitor_ids: set[str]) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) < 2:
        raise TournamentError(f"{name} must contain at least two joint scenarios")
    if len(value) > 5000:
        raise TournamentError(f"{name} cannot contain more than 5000 joint scenarios")
    result = []
    seen: set[str] = set()
    probability_total = 0.0
    asset_ids: set[str] | None = None
    for index, raw in enumerate(value):
        where = f"{name}[{index}]"
        item = _fields(raw, {"scenario_id", "probability", "asset_net_returns", "competitor_returns"}, set(), where)
        scenario_id = _text(item["scenario_id"], f"{where}.scenario_id")
        if scenario_id in seen:
            raise TournamentError(f"{where}.scenario_id is duplicated")
        seen.add(scenario_id)
        probability = _number(item["probability"], f"{where}.probability", minimum=0)
        if probability <= 0:
            raise TournamentError(f"{where}.probability must be greater than zero")
        raw_assets = item["asset_net_returns"]
        raw_competitors = item["competitor_returns"]
        if type(raw_assets) is not dict or not raw_assets:
            raise TournamentError(f"{where}.asset_net_returns must be a non-empty object")
        if type(raw_competitors) is not dict or set(raw_competitors) != competitor_ids:
            raise TournamentError(f"{where}.competitor_returns must include every leaderboard participant exactly once")
        assets = {
            _text(instrument_id, f"{where}.asset_net_returns key"): _number(return_value, f"{where}.asset_net_returns[{instrument_id}]")
            for instrument_id, return_value in raw_assets.items()
        }
        if asset_ids is None:
            asset_ids = set(assets)
        elif set(assets) != asset_ids:
            raise TournamentError(f"{name} scenarios must use an identical instrument set")
        if any(return_value <= -1 for return_value in assets.values()):
            raise TournamentError(f"{where} asset returns cannot be less than or equal to -100%")
        competitors = {
            _text(competitor_id, f"{where}.competitor_returns key"): _number(return_value, f"{where}.competitor_returns[{competitor_id}]")
            for competitor_id, return_value in raw_competitors.items()
        }
        if any(return_value <= -1 for return_value in competitors.values()):
            raise TournamentError(f"{where} competitor returns cannot be less than or equal to -100%")
        probability_total += probability
        result.append({
            "scenario_id": scenario_id,
            "probability": probability,
            "asset_net_returns": assets,
            "competitor_returns": competitors,
        })
    if abs(probability_total - 1.0) > 1e-9:
        raise TournamentError(f"{name} probabilities must sum to 1 (got {probability_total:.12g})")
    return result


def _validate_case(case: Any, ruleset: Mapping[str, Any], universe: Mapping[str, Any]) -> dict[str, Any]:
    item = _fields(
        case,
        {
            "schema_version", "case_id", "decision_at_utc", "ruleset_id", "universe_version",
            "transaction_cost_model_sha256", "m7_result_sha256", "tournament_state", "portfolio_state",
            "ruin_floor_actipesos", "evidence", "scenario_models", "optimizer",
        },
        {"candidate_portfolios"},
        "tournament case",
    )
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise TournamentError("tournament case schema_version must equal 1")
    case_id = _text(item["case_id"], "case_id")
    decision_at = _instant(item["decision_at_utc"], "decision_at_utc")
    if _text(item["ruleset_id"], "ruleset_id") != ruleset.get("ruleset_id"):
        raise TournamentError("case ruleset_id does not match the verified M1 rules snapshot")
    if _text(item["universe_version"], "universe_version") != universe.get("snapshot_id"):
        raise TournamentError("case universe_version does not match the verified M1 universe snapshot")
    _sha(item["transaction_cost_model_sha256"], "transaction_cost_model_sha256")
    m7_digest = _sha(item["m7_result_sha256"], "m7_result_sha256", nullable=True)

    state = _fields(item["tournament_state"], {"subject_competitor_id", "current_capital_actipesos", "sessions_remaining", "total_sessions", "leaderboard_snapshot"}, set(), "tournament_state")
    subject_id = _text(state["subject_competitor_id"], "tournament_state.subject_competitor_id")
    capital = _number(state["current_capital_actipesos"], "tournament_state.current_capital_actipesos", minimum=0.01)
    remaining = _integer(state["sessions_remaining"], "tournament_state.sessions_remaining", minimum=1)
    total_sessions = _integer(state["total_sessions"], "tournament_state.total_sessions", minimum=1)
    if remaining > total_sessions:
        raise TournamentError("sessions_remaining cannot exceed total_sessions")
    board = _fields(state["leaderboard_snapshot"], {"as_of_utc", "complete", "competitors"}, set(), "leaderboard_snapshot")
    board_as_of = _instant(board["as_of_utc"], "leaderboard_snapshot.as_of_utc")
    if board_as_of > decision_at:
        raise TournamentError("leaderboard snapshot was not available at decision time")
    if type(board["complete"]) is not bool:
        raise TournamentError("leaderboard_snapshot.complete must be boolean")
    if type(board["competitors"]) is not list:
        raise TournamentError("leaderboard_snapshot.competitors must be an array")
    competitors: dict[str, float] = {}
    for index, rival in enumerate(board["competitors"]):
        rival = _fields(rival, {"competitor_id", "current_capital_actipesos"}, set(), f"leaderboard_snapshot.competitors[{index}]")
        rival_id = _text(rival["competitor_id"], f"competitors[{index}].competitor_id")
        if rival_id in competitors:
            raise TournamentError(f"duplicate competitor_id {rival_id!r}")
        competitors[rival_id] = _number(rival["current_capital_actipesos"], f"competitors[{index}].current_capital_actipesos", minimum=0.01)
    if board["complete"] and not competitors:
        raise TournamentError("a complete leaderboard snapshot must include competitors")
    if subject_id in competitors:
        raise TournamentError("leaderboard_snapshot.competitors must exclude the subject participant")

    portfolio = _fields(item["portfolio_state"], {"cash_actipesos", "holdings", "traded_instrument_ids", "cumulative_purchase_value_actipesos_by_instrument"}, set(), "portfolio_state")
    cash = _number(portfolio["cash_actipesos"], "portfolio_state.cash_actipesos", minimum=0)
    if type(portfolio["holdings"]) is not list:
        raise TournamentError("portfolio_state.holdings must be an array")
    holdings: dict[str, float] = {}
    for index, holding in enumerate(portfolio["holdings"]):
        holding = _fields(holding, {"instrument_id", "market_value_actipesos"}, set(), f"portfolio_state.holdings[{index}]")
        instrument_id = _text(holding["instrument_id"], f"holdings[{index}].instrument_id")
        if instrument_id in holdings:
            raise TournamentError(f"duplicate holding {instrument_id!r}")
        value = _number(holding["market_value_actipesos"], f"holdings[{index}].market_value_actipesos", minimum=0)
        if value > 0:
            holdings[instrument_id] = value
    if abs(cash + sum(holdings.values()) - capital) > max(0.02, capital * 1e-8):
        raise TournamentError("cash plus current holdings must equal current portfolio capital")
    if type(portfolio["traded_instrument_ids"]) is not list or any(type(value) is not str for value in portfolio["traded_instrument_ids"]):
        raise TournamentError("traded_instrument_ids must be an array of instrument IDs")
    traded_values = [_text(value, "traded_instrument_ids item") for value in portfolio["traded_instrument_ids"]]
    if len(traded_values) != len(set(traded_values)):
        raise TournamentError("traded_instrument_ids must not contain duplicates")
    traded_ids = set(traded_values)
    raw_purchases = portfolio["cumulative_purchase_value_actipesos_by_instrument"]
    if type(raw_purchases) is not dict:
        raise TournamentError("cumulative_purchase_value_actipesos_by_instrument must be an object")
    purchases = {
        _text(instrument_id, "cumulative purchase instrument_id"): _number(value, f"cumulative purchases[{instrument_id}]", minimum=0)
        for instrument_id, value in raw_purchases.items()
    }
    universe_ids = {record["instrument_id"] for record in universe["instruments"]}
    unverified_state_ids = (set(holdings) | traded_ids | set(purchases)) - universe_ids
    if unverified_state_ids:
        raise TournamentError(
            "portfolio state contains instrument IDs outside the verified M1 universe: "
            + ", ".join(sorted(unverified_state_ids))
        )

    ruin_floor = _number(item["ruin_floor_actipesos"], "ruin_floor_actipesos", minimum=0.01)
    if ruin_floor >= capital:
        raise TournamentError("ruin_floor_actipesos must be below current capital")

    evidence = _fields(
        item["evidence"],
        {"sample_type", "alpha_source_available_at_utc", "scenario_source_available_at_utc", "leaderboard_source_available_at_utc", "final_holdout_locked", "source_manifest_sha256"},
        set(),
        "evidence",
    )
    sample_type = evidence["sample_type"]
    if sample_type not in {"authorized_point_in_time", "synthetic_fixture"}:
        raise TournamentError("evidence.sample_type must be authorized_point_in_time or synthetic_fixture")
    availability = {
        key: _instant(evidence[key], f"evidence.{key}")
        for key in ("alpha_source_available_at_utc", "scenario_source_available_at_utc", "leaderboard_source_available_at_utc")
    }
    if any(value > decision_at for value in availability.values()):
        raise TournamentError("an alpha, scenario, or leaderboard input was unavailable at decision time")
    if availability["leaderboard_source_available_at_utc"] > board_as_of:
        raise TournamentError("leaderboard source availability is after the leaderboard snapshot timestamp")
    if type(evidence["final_holdout_locked"]) is not bool:
        raise TournamentError("evidence.final_holdout_locked must be boolean")
    if not evidence["final_holdout_locked"]:
        raise TournamentError("selection requires a locked holdout split")
    manifest_sha = _sha(evidence["source_manifest_sha256"], "evidence.source_manifest_sha256", nullable=True)
    if sample_type == "authorized_point_in_time" and (manifest_sha is None or not evidence["final_holdout_locked"]):
        raise TournamentError("authorized evidence requires a source manifest and locked holdout")

    optimizer = _fields(
        item["optimizer"],
        {"seed", "candidate_count", "max_active_positions", "holdout_draws", "late_stage_fraction", "defend_p1_tolerance", "catch_up_p1_tolerance"},
        set(),
        "optimizer",
    )
    seed = _integer(optimizer["seed"], "optimizer.seed", maximum=2**32 - 1)
    candidate_count = _integer(optimizer["candidate_count"], "optimizer.candidate_count", minimum=1, maximum=2000)
    max_active = _integer(optimizer["max_active_positions"], "optimizer.max_active_positions", minimum=5, maximum=207)
    holdout_draws = _integer(optimizer["holdout_draws"], "optimizer.holdout_draws", minimum=100, maximum=100000)
    late_fraction = _number(optimizer["late_stage_fraction"], "optimizer.late_stage_fraction", minimum=0, maximum=1)
    defend_tolerance = _number(optimizer["defend_p1_tolerance"], "optimizer.defend_p1_tolerance", minimum=0, maximum=1)
    catchup_tolerance = _number(optimizer["catch_up_p1_tolerance"], "optimizer.catch_up_p1_tolerance", minimum=0, maximum=1)

    if type(item["scenario_models"]) is not list or not item["scenario_models"]:
        raise TournamentError("scenario_models must be a non-empty array")
    if len(item["scenario_models"]) > 20:
        raise TournamentError("scenario_models cannot contain more than 20 leaderboard assumptions")
    models: list[dict[str, Any]] = []
    model_ids: set[str] = set()
    for index, raw_model in enumerate(item["scenario_models"]):
        where = f"scenario_models[{index}]"
        model = _fields(raw_model, {"model_id", "fit_cutoff_utc", "scenario_horizon_sessions", "return_basis", "source_sha256", "selection_scenarios", "holdout_scenarios"}, set(), where)
        model_id = _text(model["model_id"], f"{where}.model_id")
        if model_id in model_ids:
            raise TournamentError(f"duplicate scenario model {model_id!r}")
        model_ids.add(model_id)
        fit_cutoff = _instant(model["fit_cutoff_utc"], f"{where}.fit_cutoff_utc")
        if fit_cutoff > decision_at:
            raise TournamentError(f"{where}.fit_cutoff_utc is after decision time")
        if availability["alpha_source_available_at_utc"] > fit_cutoff:
            raise TournamentError(f"{where} alpha data was not available by its fit cutoff")
        if availability["scenario_source_available_at_utc"] > fit_cutoff:
            raise TournamentError(f"{where} scenario source was not available by its fit cutoff")
        horizon = _integer(model["scenario_horizon_sessions"], f"{where}.scenario_horizon_sessions", minimum=1)
        if horizon != remaining:
            raise TournamentError(f"{where} horizon must equal sessions_remaining")
        if model["return_basis"] != "net_of_costs":
            raise TournamentError(f"{where}.return_basis must be net_of_costs; M8 will not apply costs twice")
        source_sha = _sha(model["source_sha256"], f"{where}.source_sha256")
        selection = _scenario_rows(model["selection_scenarios"], f"{where}.selection_scenarios", set(competitors))
        holdout = _scenario_rows(model["holdout_scenarios"], f"{where}.holdout_scenarios", set(competitors))
        if set(selection[0]["asset_net_returns"]) != set(holdout[0]["asset_net_returns"]):
            raise TournamentError(f"{where} selection and holdout scenarios must use the same instrument set")
        models.append({
            "model_id": model_id,
            "fit_cutoff_utc": fit_cutoff,
            "horizon": horizon,
            "source_sha256": source_sha,
            "selection_scenarios": selection,
            "holdout_scenarios": holdout,
        })
    if "base" not in model_ids:
        raise TournamentError("scenario_models must include model_id 'base'")

    candidates = item.get("candidate_portfolios", [])
    if type(candidates) is not list:
        raise TournamentError("candidate_portfolios must be an array when supplied")
    if len(candidates) > 2000:
        raise TournamentError("candidate_portfolios cannot contain more than 2000 supplied allocations")
    clean_candidates = []
    for index, raw_candidate in enumerate(candidates):
        candidate = _fields(raw_candidate, {"candidate_id", "weights"}, set(), f"candidate_portfolios[{index}]")
        weights = candidate["weights"]
        if type(weights) is not dict:
            raise TournamentError(f"candidate_portfolios[{index}].weights must be an object")
        clean_candidates.append({
            "candidate_id": _text(candidate["candidate_id"], f"candidate_portfolios[{index}].candidate_id"),
            "weights": {
                _text(instrument_id, "candidate instrument_id"): _number(value, f"candidate weight[{instrument_id}]", minimum=0, maximum=0.5)
                for instrument_id, value in weights.items()
            },
        })

    base_model = next(model for model in models if model["model_id"] == "base")
    selection_work = (
        candidate_count + max_active + len(universe["instruments"]) + 2 + len(clean_candidates)
    ) * len(base_model["selection_scenarios"]) * max_active
    holdout_work = holdout_draws * max_active * len(models) * 3
    if selection_work > 30_000_000 or holdout_work > 30_000_000:
        raise TournamentError(
            "configured optimizer exceeds the 30-million portfolio-scenario work budget; "
            "reduce candidate_count, scenario rows, max_active_positions, holdout_draws, or model count"
        )

    return {
        "case_id": case_id,
        "decision_at": decision_at,
        "ruleset_id": item["ruleset_id"],
        "universe_version": item["universe_version"],
        "transaction_cost_model_sha256": item["transaction_cost_model_sha256"],
        "m7_result_sha256": m7_digest,
        "capital": capital,
        "subject_competitor_id": subject_id,
        "sessions_remaining": remaining,
        "total_sessions": total_sessions,
        "board_complete": board["complete"],
        "board_as_of": board_as_of,
        "competitors": competitors,
        "cash": cash,
        "holdings": holdings,
        "traded_ids": traded_ids,
        "purchases": purchases,
        "ruin_floor": ruin_floor,
        "sample_type": sample_type,
        "manifest_sha256": manifest_sha,
        "final_holdout_locked": evidence["final_holdout_locked"],
        "optimizer": {
            "seed": seed,
            "candidate_count": candidate_count,
            "max_active_positions": max_active,
            "holdout_draws": holdout_draws,
            "late_stage_fraction": late_fraction,
            "defend_p1_tolerance": defend_tolerance,
            "catch_up_p1_tolerance": catchup_tolerance,
        },
        "scenario_models": models,
        "candidate_portfolios": clean_candidates,
        "case_sha256": canonical_sha256(case),
    }


def _no_decision(case: Mapping[str, Any], reason: str, *, forecast_status: str = "NO_DECISION", m7_sha: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "software_status": "PASS",
        "decision_status": "NO_DECISION",
        "empirical_gate": "NEEDS_MORE_EVIDENCE",
        "forecast_status": forecast_status,
        "input_trace": {
            "case_id": case["case_id"],
            "case_sha256": case["case_sha256"],
            "m7_result_sha256": m7_sha or case["m7_result_sha256"],
            "verified_universe_version": case["universe_version"],
            "ruleset_id": case["ruleset_id"],
        },
        "decision": None,
        "mode": {"value": "NOT_EVALUATED", "reason": reason},
        "candidate_search": {"requested_random_candidates": case["optimizer"]["candidate_count"], "feasible_count": 0, "rejected_count": 0},
        "comparisons": [],
        "leaderboard_sensitivity": [],
        "limitations": [reason, "No trade or portfolio recommendation is emitted."],
    }


def _m7_live_instruments(m7: Any, case: Mapping[str, Any], m7_sha: str | None) -> tuple[set[str], str | None]:
    if m7 is None:
        return set(), "No M7 result artifact was supplied."
    if case["m7_result_sha256"] is None or m7_sha is None or case["m7_result_sha256"] != m7_sha:
        raise TournamentError("M7 result file SHA-256 does not match case.m7_result_sha256")
    if type(m7) is not dict or m7.get("schema_version") != 1 or m7.get("software_status") != "PASS":
        raise TournamentError("M7 result must be a successful version 1 ensemble result")
    forecast_status = m7.get("forecast_status")
    if forecast_status == "NO_PROMOTED_SIGNALS":
        return set(), "M7 reports NO_PROMOTED_SIGNALS."
    if forecast_status != "CALIBRATED":
        return set(), f"M7 forecast_status is {forecast_status!r}; calibrated forecasts are required."
    trace = m7.get("input_trace")
    if type(trace) is not dict:
        raise TournamentError("M7 result input_trace must be an object")
    if trace.get("verified_universe_version") != case["universe_version"]:
        raise TournamentError("M7 verified universe does not match the M8 case")
    if trace.get("transaction_cost_model_sha256") != case["transaction_cost_model_sha256"]:
        raise TournamentError("M7 transaction cost model does not match the M8 case")
    predictions = m7.get("predictions")
    if type(predictions) is not list:
        raise TournamentError("M7 result predictions must be an array")
    live_ids = set()
    for index, prediction in enumerate(predictions):
        if type(prediction) is not dict or prediction.get("split") != "live":
            continue
        if prediction.get("forecast_status") != "CALIBRATED_OOS_MODEL" or type(prediction.get("distribution")) is not dict:
            continue
        decision_at = _instant(prediction.get("decision_at_utc"), f"M7 predictions[{index}].decision_at_utc")
        if decision_at != case["decision_at"]:
            raise TournamentError("M7 LIVE forecasts must have the same decision timestamp as the M8 case")
        instrument_id = _text(prediction.get("instrument_id"), f"M7 predictions[{index}].instrument_id")
        horizon = _integer(prediction.get("horizon_sessions"), f"M7 predictions[{index}].horizon_sessions", minimum=1)
        if horizon != case["sessions_remaining"]:
            raise TournamentError("M7 forecast horizon must cover the complete remaining tournament scenario horizon")
        if instrument_id in live_ids:
            raise TournamentError(f"M7 has duplicate LIVE forecast for {instrument_id!r}")
        live_ids.add(instrument_id)
    if not live_ids:
        return set(), "M7 has no calibrated LIVE forecasts for the current decision timestamp."
    if m7.get("empirical_gate") != "PASS":
        return live_ids, "M7 empirical gate is not PASS; comparisons remain simulation-only."
    return live_ids, None


def _m1_checks(
    weights: Mapping[str, float],
    case: Mapping[str, Any],
    ruleset: Mapping[str, Any],
    universe: Mapping[str, Any],
    instrument_records: Mapping[str, Mapping[str, Any]],
    as_of: date,
) -> tuple[bool, dict[str, Any]]:
    if not weights or sum(weights.values()) > 1 + POSITION_CAP_TOLERANCE:
        return False, {"constraint_status": "FAIL", "checks": [{"check_id": "long_only_budget", "status": "FAIL"}]}
    if any(value < 0 or value > 0.5 + POSITION_CAP_TOLERANCE for value in weights.values()):
        return False, {"constraint_status": "FAIL", "checks": [{"check_id": "long_only_and_concentration", "status": "FAIL"}]}
    unknown = sorted(set(weights) - instrument_records.keys())
    if unknown:
        return False, {"constraint_status": "FAIL", "checks": [{"check_id": "verified_m1_universe", "status": "FAIL", "detail": str(unknown)}]}

    current_weights = {key: value / case["capital"] for key, value in case["holdings"].items()}
    buy_values = {
        instrument_id: max(0.0, weights.get(instrument_id, 0.0) - current_weights.get(instrument_id, 0.0)) * case["capital"]
        for instrument_id in set(weights) | set(current_weights)
    }
    sells = sum(max(0.0, current_weights.get(key, 0.0) - weights.get(key, 0.0)) * case["capital"] for key in set(weights) | set(current_weights))
    buys = sum(buy_values.values())
    available = case["cash"] + sells
    checks = [{
        "check_id": "long_only_buying_power",
        "status": "PASS" if buys <= available + max(0.02, case["capital"] * 1e-10) else "FAIL",
        "buys_actipesos": round(buys, 4),
        "cash_plus_sale_proceeds_actipesos": round(available, 4),
    }]
    share_buys = {
        key: value for key, value in buy_values.items()
        if instrument_records[key]["category"] in EQUITY_CATEGORIES
    }
    cap = float(ruleset["rules"]["portfolio_constraints"]["maximum_single_share_purchase_to_portfolio_value"])
    purchase_violations = {
        key: case["purchases"].get(key, 0.0) + value
        for key, value in share_buys.items()
        if case["purchases"].get(key, 0.0) + value > case["capital"] * cap + max(0.02, case["capital"] * 1e-10)
    }
    checks.append({
        "check_id": "cumulative_single_share_purchase_cap",
        "status": "FAIL" if purchase_violations else "PASS",
        "violations": purchase_violations,
    })

    new_trades = {key for key, value in share_buys.items() if value > 0.01}
    all_traded = case["traded_ids"] | new_trades
    traded_shares = {
        key for key in all_traded
        if key in instrument_records and instrument_records[key]["category"] in EQUITY_CATEGORIES
    }
    held_or_traded = set(case["holdings"]) | set(weights) | all_traded
    constraints = ruleset["rules"]["portfolio_constraints"]
    checks.append({
        "check_id": "minimum_distinct_guide_instruments",
        "status": "PASS" if len(held_or_traded) >= constraints["minimum_distinct_guide_instruments"] else "FAIL",
        "count": len(held_or_traded),
        "minimum": constraints["minimum_distinct_guide_instruments"],
    })
    checks.append({
        "check_id": "minimum_distinct_traded_shares_strict_interpretation",
        "status": "PASS" if len(traded_shares) >= constraints["minimum_distinct_traded_shares"] else "FAIL",
        "count": len(traded_shares),
        "minimum": constraints["minimum_distinct_traded_shares"],
    })

    holdings = [
        {
            "instrument_id": instrument_id,
            "quantity": 1,
            "market_value_actipesos": f"{value * case['capital']:.8f}",
        }
        for instrument_id, value in weights.items()
        if value > 0
    ]
    cumulative = dict(case["purchases"])
    for instrument_id, value in share_buys.items():
        cumulative[instrument_id] = cumulative.get(instrument_id, 0.0) + value
    portfolio_input = {
        "holdings": holdings,
        "traded_instrument_ids": sorted(case["traded_ids"] | new_trades),
        "portfolio_value_actipesos": f"{case['capital']:.8f}",
        "cumulative_purchase_value_actipesos_by_instrument": {
            key: f"{value:.8f}" for key, value in cumulative.items()
        },
    }
    m1_result = validate_portfolio(portfolio_input, ruleset, universe, as_of)
    checks.append({
        "check_id": "m1_portfolio_constraint_engine",
        "status": "PASS" if m1_result["constraint_status"] == "COMPLIANT" else "FAIL",
        "constraint_status": m1_result["constraint_status"],
        "official_award_eligibility_status": m1_result["official_award_eligibility_status"],
        "source_ambiguities": m1_result["source_ambiguities"],
    })
    feasible = all(check["status"] == "PASS" for check in checks)
    return feasible, {
        "constraint_status": "PASS" if feasible else "FAIL",
        "official_award_eligibility_status": m1_result["official_award_eligibility_status"],
        "checks": checks,
        "source_ambiguities": m1_result["source_ambiguities"],
    }


def _cap_weights(raw_weights: Sequence[float], total: float, cap: float = 0.5) -> list[float]:
    if not raw_weights:
        return []
    remaining = total
    active = set(range(len(raw_weights)))
    output = [0.0] * len(raw_weights)
    while active:
        weight_total = sum(raw_weights[index] for index in active)
        if weight_total <= 0:
            share = remaining / len(active)
            for index in active:
                output[index] = min(cap, share)
            break
        capped = [index for index in active if remaining * raw_weights[index] / weight_total > cap]
        if not capped:
            for index in active:
                output[index] = remaining * raw_weights[index] / weight_total
            break
        for index in capped:
            output[index] = cap
            remaining -= cap
            active.remove(index)
    return output


def _generate_candidates(case: Mapping[str, Any], asset_ids: Sequence[str]) -> list[dict[str, Any]]:
    if len(asset_ids) < 5:
        return []
    optimizer = case["optimizer"]
    max_positions = min(optimizer["max_active_positions"], len(asset_ids))
    rng = random.Random(optimizer["seed"])
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(candidate_id: str, weights: Mapping[str, float]) -> None:
        clean = {key: float(value) for key, value in sorted(weights.items()) if value > POSITION_CAP_TOLERANCE}
        signature = canonical_sha256(clean)
        if signature in seen:
            return
        seen.add(signature)
        candidates.append({"candidate_id": candidate_id, "weights": clean})

    current = {key: value / case["capital"] for key, value in case["holdings"].items() if key in asset_ids}
    if current:
        add("current_portfolio", current)
    base_ids = sorted(asset_ids)[:max_positions]
    equal_weight = {key: 1.0 / len(base_ids) for key in base_ids}
    add("equal_weight", equal_weight)
    for anchor in sorted(asset_ids):
        others = [key for key in sorted(asset_ids) if key != anchor][:max_positions - 1]
        selected = [anchor, *others]
        if len(selected) < 5:
            continue
        rest_weight = 0.5 / len(others)
        add(f"concentrated_{anchor}", {anchor: 0.5, **{key: rest_weight for key in others}})

    attempts = 0
    random_added = 0
    target = optimizer["candidate_count"]
    while random_added < target and attempts < max(target * 30, 100):
        attempts += 1
        position_count = rng.randint(5, max_positions)
        selected = rng.sample(list(asset_ids), position_count)
        raw = [rng.expovariate(1.0) for _ in selected]
        invested = rng.uniform(0.5, 1.0)
        capped = _cap_weights(raw, invested)
        previous_count = len(candidates)
        add(f"random_{optimizer['seed']}_{attempts:05d}", dict(zip(selected, capped, strict=True)))
        if len(candidates) > previous_count:
            random_added += 1
    return candidates


def _portfolio_stats(weights: Mapping[str, float], scenarios: Sequence[Mapping[str, Any]], case: Mapping[str, Any]) -> dict[str, Any]:
    returns = []
    ranks = []
    wins = 0.0
    ruin = 0.0
    ties = 0.0
    for scenario in scenarios:
        probability = scenario["probability"]
        portfolio_return = sum(weight * scenario["asset_net_returns"][instrument_id] for instrument_id, weight in weights.items())
        final_capital = case["capital"] * (1.0 + portfolio_return)
        rival_capitals = [case["competitors"][competitor_id] * (1.0 + rival_return) for competitor_id, rival_return in scenario["competitor_returns"].items()]
        top_rival = max(rival_capitals)
        is_unique_first = final_capital > top_rival + max(0.01, case["capital"] * 1e-12)
        is_tied_first = abs(final_capital - top_rival) <= max(0.01, case["capital"] * 1e-12)
        wins += probability if is_unique_first else 0.0
        ties += probability if is_tied_first else 0.0
        ruin += probability if final_capital < case["ruin_floor"] else 0.0
        rank = 1 + sum(rival_capital > final_capital for rival_capital in rival_capitals)
        ranks.append((float(rank), probability))
        returns.append((portfolio_return, probability))
    expected_return = sum(value * probability for value, probability in returns)
    variance = sum(probability * (value - expected_return) ** 2 for value, probability in returns)
    standard_deviation = math.sqrt(max(0.0, variance))
    return {
        "expected_net_return": expected_return,
        "scenario_standard_deviation": standard_deviation,
        "horizon_sharpe": expected_return / standard_deviation if standard_deviation > 1e-12 else None,
        "unique_first_probability": wins,
        "tie_for_first_probability": ties,
        "ruin_probability": ruin,
        "expected_final_rank": sum(value * probability for value, probability in ranks),
        "q05_net_return": _weighted_quantile(returns, 0.05),
        "q95_net_return": _weighted_quantile(returns, 0.95),
    }


def _monte_carlo_stats(weights: Mapping[str, float], scenarios: Sequence[Mapping[str, Any]], case: Mapping[str, Any], draws: Sequence[int]) -> dict[str, Any]:
    sample_returns = []
    sample_ranks = []
    wins = ties = ruin = 0
    for index in draws:
        scenario = scenarios[index]
        portfolio_return = sum(weight * scenario["asset_net_returns"][instrument_id] for instrument_id, weight in weights.items())
        final_capital = case["capital"] * (1.0 + portfolio_return)
        rival_capitals = [case["competitors"][competitor_id] * (1.0 + rival_return) for competitor_id, rival_return in scenario["competitor_returns"].items()]
        top_rival = max(rival_capitals)
        epsilon = max(0.01, case["capital"] * 1e-12)
        wins += int(final_capital > top_rival + epsilon)
        ties += int(abs(final_capital - top_rival) <= epsilon)
        ruin += int(final_capital < case["ruin_floor"])
        sample_returns.append(portfolio_return)
        sample_ranks.append(1 + sum(rival_capital > final_capital for rival_capital in rival_capitals))
    count = len(draws)
    p1 = wins / count
    z = 1.959963984540054
    denom = 1 + z * z / count
    center = (p1 + z * z / (2 * count)) / denom
    half = z * math.sqrt(p1 * (1 - p1) / count + z * z / (4 * count * count)) / denom
    std = pstdev(sample_returns) if count > 1 else 0.0
    return {
        "monte_carlo_draws": count,
        "unique_first_probability": p1,
        "unique_first_probability_wilson_95": [max(0.0, center - half), min(1.0, center + half)],
        "tie_for_first_probability": ties / count,
        "ruin_probability": ruin / count,
        "expected_net_return": mean(sample_returns),
        "scenario_standard_deviation": std,
        "horizon_sharpe": mean(sample_returns) / std if std > 1e-12 else None,
        "expected_final_rank": mean(sample_ranks),
        "q05_net_return": sorted(sample_returns)[max(0, math.ceil(0.05 * count) - 1)],
        "q95_net_return": sorted(sample_returns)[max(0, math.ceil(0.95 * count) - 1)],
    }


def _policy_mode(case: Mapping[str, Any]) -> dict[str, Any]:
    current_rank = 1 + sum(value > case["capital"] for value in case["competitors"].values())
    leader_capital = max(case["competitors"].values())
    gap = leader_capital - case["capital"]
    remaining_fraction = case["sessions_remaining"] / case["total_sessions"]
    if current_rank == 1:
        mode = "DEFEND"
        reason = "current capital is tied for or above the recorded leaderboard"
    elif remaining_fraction <= case["optimizer"]["late_stage_fraction"]:
        mode = "CATCH_UP"
        reason = "the participant trails and the remaining-session fraction is in the preregistered late-stage range"
    else:
        mode = "NEUTRAL"
        reason = "the participant trails but enough sessions remain for neutral rank-aware selection"
    return {
        "value": mode,
        "reason": reason,
        "current_rank_from_snapshot": current_rank,
        "leader_capital_actipesos": leader_capital,
        "leader_gap_actipesos": gap,
        "remaining_session_fraction": remaining_fraction,
        "late_stage_fraction_threshold": case["optimizer"]["late_stage_fraction"],
    }


def _candidate_selection(stats: Mapping[str, Mapping[str, Any]], mode: str, case: Mapping[str, Any]) -> dict[str, str]:
    best_p1 = max(value["unique_first_probability"] for value in stats.values())
    tolerance = case["optimizer"]["defend_p1_tolerance"] if mode == "DEFEND" else case["optimizer"]["catch_up_p1_tolerance"]
    near_best = [
        candidate_id for candidate_id, value in stats.items()
        if value["unique_first_probability"] + tolerance >= best_p1
    ]
    if mode == "DEFEND":
        rank_selected = min(
            near_best,
            key=lambda key: (stats[key]["ruin_probability"], stats[key]["scenario_standard_deviation"], -stats[key]["unique_first_probability"], key),
        )
    elif mode == "CATCH_UP":
        rank_selected = min(
            near_best,
            key=lambda key: (-stats[key]["q95_net_return"], -stats[key]["unique_first_probability"], stats[key]["ruin_probability"], key),
        )
    else:
        rank_selected = min(
            stats,
            key=lambda key: (-stats[key]["unique_first_probability"], -stats[key]["expected_net_return"], stats[key]["ruin_probability"], key),
        )
    return_stats = max(stats, key=lambda key: (stats[key]["expected_net_return"], -stats[key]["ruin_probability"], key))
    sharpe_ids = [key for key, value in stats.items() if value["horizon_sharpe"] is not None]
    sharpe_stats = max(sharpe_ids, key=lambda key: (stats[key]["horizon_sharpe"], stats[key]["expected_net_return"], key)) if sharpe_ids else return_stats
    return {
        "rank_aware": rank_selected,
        "expected_return": return_stats,
        "sharpe": sharpe_stats,
    }


def _candidate_feasibility(
    candidate: Mapping[str, Any],
    case: Mapping[str, Any],
    ruleset: Mapping[str, Any],
    universe: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    as_of: date,
    live_instrument_ids: set[str],
) -> tuple[bool, dict[str, Any]]:
    weights = candidate["weights"]
    if not weights or set(weights) - live_instrument_ids:
        return False, {"constraint_status": "FAIL", "checks": [{"check_id": "m7_live_forecast_coverage", "status": "FAIL"}]}
    valid, report = _m1_checks(weights, case, ruleset, universe, records, as_of)
    active_equities = {
        key for key, value in weights.items()
        if value > POSITION_CAP_TOLERANCE and records[key]["category"] in EQUITY_CATEGORIES
    }
    if len(active_equities) < 5:
        report["checks"].append({"check_id": "minimum_five_equity_positions", "status": "FAIL", "count": len(active_equities)})
        valid = False
    return valid, report


def evaluate_tournament(
    case: Any,
    m7_result: Any,
    *,
    m7_result_sha256: str | None,
    ruleset: Mapping[str, Any],
    universe: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare feasible target allocations under M7 forecasts and joint scenarios.

    Even a successful comparison emits no trade instruction. The live M7
    empirical gate remains an independent requirement for any financial claim.
    """
    clean = _validate_case(case, ruleset, universe)
    if not clean["board_complete"]:
        return _no_decision(clean, "P(final_rank=1) requires a complete or explicitly modelled leaderboard snapshot.")
    live_ids, m7_reason = _m7_live_instruments(m7_result, clean, m7_result_sha256)
    if m7_reason and not live_ids:
        return _no_decision(clean, m7_reason, forecast_status=(m7_result or {}).get("forecast_status", "NO_DECISION") if type(m7_result) is dict else "NO_DECISION", m7_sha=m7_result_sha256)

    base_model = next(model for model in clean["scenario_models"] if model["model_id"] == "base")
    raw_scenario_assets = set(base_model["selection_scenarios"][0]["asset_net_returns"])
    for model in clean["scenario_models"]:
        for split_name in ("selection_scenarios", "holdout_scenarios"):
            if set(model[split_name][0]["asset_net_returns"]) != raw_scenario_assets:
                raise TournamentError("all scenario models must use the same instrument set")
    if raw_scenario_assets - live_ids:
        raise TournamentError("scenario bank contains instruments without a calibrated M7 LIVE forecast")

    try:
        rule_date = clean["decision_at"].astimezone(ZoneInfo("America/Mexico_City")).date()
    except Exception as exc:  # pragma: no cover - zone database failure is environment-specific
        raise TournamentError(f"cannot resolve M1 rule date: {exc}") from exc
    eligible_ids = {
        record["instrument_id"]
        for record in eligible_instruments(universe, rule_date)
        if record["category"] in EQUITY_CATEGORIES
        and not record["eligibility"].get("rulebook_category_conflict")
    }
    records = {record["instrument_id"]: record for record in universe["instruments"]}
    if raw_scenario_assets - eligible_ids:
        raise TournamentError("scenario bank contains an instrument not eligible as of the M1 decision date")
    assets = sorted(raw_scenario_assets)
    if len(assets) < 5:
        return _no_decision(clean, "Fewer than five source-verified, eligible equity forecasts are available.", forecast_status="CALIBRATED", m7_sha=m7_result_sha256)

    mode = _policy_mode(clean)
    generated = _generate_candidates(clean, assets)
    generated.extend(clean["candidate_portfolios"])
    candidate_ids: set[str] = set()
    feasible: list[dict[str, Any]] = []
    rejected = []
    for candidate in generated:
        candidate_id = candidate["candidate_id"]
        if candidate_id in candidate_ids:
            candidate_id = f"{candidate_id}_{canonical_sha256(candidate['weights'])[:8]}"
        candidate_ids.add(candidate_id)
        valid, report = _candidate_feasibility(candidate, clean, ruleset, universe, records, rule_date, live_ids)
        if valid:
            feasible.append({"candidate_id": candidate_id, "weights": candidate["weights"], "constraints": report})
        else:
            rejected.append({"candidate_id": candidate_id, "constraints": report})
    if not feasible:
        result = _no_decision(clean, "The candidate generator found no portfolio satisfying the strict M1 constraints.", forecast_status="CALIBRATED", m7_sha=m7_result_sha256)
        result["candidate_search"] = {"requested_random_candidates": clean["optimizer"]["candidate_count"], "feasible_count": 0, "rejected_count": len(rejected), "rejections": rejected[:20]}
        return result

    selection_scenarios = base_model["selection_scenarios"]
    selection_stats = {
        candidate["candidate_id"]: _portfolio_stats(candidate["weights"], selection_scenarios, clean)
        for candidate in feasible
    }
    selected = _candidate_selection(selection_stats, mode["value"], clean)
    selected_ids = list(dict.fromkeys(selected.values()))
    selected_candidates = {candidate["candidate_id"]: candidate for candidate in feasible if candidate["candidate_id"] in selected_ids}
    comparison_rows = []
    sensitivity = []
    for model in clean["scenario_models"]:
        holdout = model["holdout_scenarios"]
        rng_seed = int.from_bytes(hashlib.sha256(f"{clean['optimizer']['seed']}|{model['model_id']}|holdout".encode("utf-8")).digest()[:8], "big")
        rng = random.Random(rng_seed)
        draw_indices = rng.choices(range(len(holdout)), weights=[row["probability"] for row in holdout], k=clean["optimizer"]["holdout_draws"])
        model_evaluations = {}
        for role, candidate_id in selected.items():
            candidate = selected_candidates[candidate_id]
            model_evaluations[role] = {
                "candidate_id": candidate_id,
                "weights": candidate["weights"],
                "holdout": _monte_carlo_stats(candidate["weights"], holdout, clean, draw_indices),
                "selection": selection_stats[candidate_id],
                "m1_constraints": candidate["constraints"],
            }
        sensitivity.append({"model_id": model["model_id"], "monte_carlo_seed": rng_seed, "comparisons": model_evaluations})
        if model["model_id"] == "base":
            for role in ("rank_aware", "expected_return", "sharpe"):
                comparison_rows.append({"strategy": role, **model_evaluations[role]})

    by_strategy = {row["strategy"]: row for row in comparison_rows}
    rank_metrics = by_strategy["rank_aware"]["holdout"]
    return_metrics = by_strategy["expected_return"]["holdout"]
    p1_delta = rank_metrics["unique_first_probability"] - return_metrics["unique_first_probability"]
    return_delta = rank_metrics["expected_net_return"] - return_metrics["expected_net_return"]
    if p1_delta > 0 and return_delta < 0:
        explanation = (
            "En este holdout simulado, el portafolio rank-aware ganó más escenarios de primer lugar pese a menor retorno esperado; "
            "la diferencia provino de la distribución conjunta y su cola derecha relativa a los rivales."
        )
    else:
        explanation = (
            "Este conjunto simulado no mostró simultáneamente mayor P(final_rank=1) y menor retorno esperado para el portafolio rank-aware."
        )
    m7_gate = m7_result.get("empirical_gate") if type(m7_result) is dict else None
    decision_status = "SIMULATION_ONLY"
    return {
        "schema_version": 1,
        "software_status": "PASS",
        "decision_status": decision_status,
        "empirical_gate": "NEEDS_MORE_EVIDENCE",
        "forecast_status": "CALIBRATED",
        "input_trace": {
            "case_id": clean["case_id"],
            "case_sha256": clean["case_sha256"],
            "m7_result_sha256": m7_result_sha256,
            "verified_universe_version": clean["universe_version"],
            "ruleset_id": clean["ruleset_id"],
            "transaction_cost_model_sha256": clean["transaction_cost_model_sha256"],
            "scenario_model_ids": [model["model_id"] for model in clean["scenario_models"]],
            "optimizer_seed": clean["optimizer"]["seed"],
        },
        "mode": mode,
        "candidate_search": {
            "requested_random_candidates": clean["optimizer"]["candidate_count"],
            "generated_candidate_count": len(generated),
            "feasible_count": len(feasible),
            "rejected_count": len(rejected),
            "rejections": rejected[:20],
            "objective_selection_split": "base.selection_scenarios",
            "holdout_split": "each_model.holdout_scenarios",
            "holdout_used_for_selection": False,
        },
        "selection": {
            "rank_aware_candidate_id": selected["rank_aware"],
            "expected_return_candidate_id": selected["expected_return"],
            "sharpe_candidate_id": selected["sharpe"],
            "selection_metrics": {key: selection_stats[key] for key in selected_ids},
            "allocation_scope": "simulation-only target weights; no order sequence or execution is generated",
        },
        "comparisons": comparison_rows,
        "rank_aware_vs_expected_return": {
            "holdout_unique_first_probability_delta": p1_delta,
            "holdout_expected_return_delta": return_delta,
            "explanation": explanation,
        },
        "leaderboard_sensitivity": sensitivity,
        "scenario_assumptions": {
            "return_basis": "net_of_costs",
            "cash_return": 0.0,
            "cash_return_assumption": "zero; no cash yield is sourced in the M1 snapshot",
            "portfolio_rebalance_fees_added": False,
            "cost_handling": "Scenario returns are declared net_of_costs and bound by the cost-model digest; M8 does not deduct fees twice. Candidate-specific transition commissions and slippage are not recalculated and must be reflected in submitted scenario returns before any empirical claim.",
            "final_rank_one_definition": "strictly greater terminal capital than every participant in the complete leaderboard snapshot",
            "ruin_definition": f"terminal capital below the user-declared floor of {clean['ruin_floor']:.2f} actipesos",
            "holdout_draws": clean["optimizer"]["holdout_draws"],
            "holdout_common_random_numbers": True,
        },
        "operational_limits": {
            "actinver_symbol_mapping": "UNVERIFIED_IN_SIMULATOR",
            "execution_fills": "NOT_SIMULATED",
            "official_award_eligibility": "INDETERMINATE_WHILE_M1_SOURCE_AMBIGUITIES_REMAIN",
            "manual_order_entry_required": True,
        },
        "decision": None,
        "limitations": [
            "All portfolio outputs are scenario comparisons, not an Actinver recommendation or order instruction.",
            "The current M7 empirical gate is NEEDS_MORE_EVIDENCE and the production M7 registry is empty.",
            "Scenario model probabilities and opponent behavior are assumptions; sensitivity results are reported separately.",
            "Portfolio-specific rebalancing fees and slippage are not recalculated; current comparisons remain simulation-only until scenarios include those costs.",
            "The finite candidate pool is a heuristic search and does not certify a global optimum.",
            "Execution fills, queue priority, slippage beyond the bound M7 cost model, and exact simulator symbols remain unverified.",
            "M1 source wording leaves award-eligibility interpretations unresolved; strict portfolio checks do not certify an award.",
        ],
    }


__all__ = ["TournamentError", "canonical_sha256", "evaluate_tournament"]
