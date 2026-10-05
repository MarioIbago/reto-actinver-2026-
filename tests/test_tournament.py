from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from actinver.m1 import eligible_instruments, load_rules, load_universe
from actinver.tournament import TournamentError, evaluate_tournament
from actinver.tournament_cli import _repository_root, main as tournament_main


ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(ROOT / "config/actinver_rules.yaml")
UNIVERSE = load_universe(ROOT / "data/metadata/actinver_universe_2026_v1.json")
DECISION_AT = "2026-10-05T20:00:00Z"
COST_SHA = "c" * 64
SOURCE_SHA = "d" * 64


def _scenario(scenario_id: str, competitor_return: float) -> dict:
    assets = {record["instrument_id"]: 0.04 for record in _assets()}
    assets[_assets()[0]["instrument_id"]] = 0.8 if scenario_id.endswith("up") else -0.8
    return {
        "scenario_id": scenario_id,
        "probability": 0.5,
        "asset_net_returns": assets,
        "competitor_returns": {"leader": competitor_return},
    }


def _assets() -> list[dict]:
    available = eligible_instruments(UNIVERSE, "2026-10-05")
    return [
        item for item in available
        if item["category"] == "national_equity"
        and not item["eligibility"].get("rulebook_category_conflict")
    ][:5]


def _model(model_id: str, competitor_return: float = 0.08) -> dict:
    return {
        "model_id": model_id,
        "fit_cutoff_utc": "2026-10-05T19:30:00Z",
        "scenario_horizon_sessions": 5,
        "return_basis": "net_of_costs",
        "source_sha256": SOURCE_SHA,
        "selection_scenarios": [
            _scenario(f"{model_id}-selection-down", competitor_return),
            _scenario(f"{model_id}-selection-up", competitor_return),
        ],
        "holdout_scenarios": [
            _scenario(f"{model_id}-holdout-down", competitor_return),
            _scenario(f"{model_id}-holdout-up", competitor_return),
        ],
    }


def tournament_case() -> dict:
    ids = [item["instrument_id"] for item in _assets()]
    return {
        "schema_version": 1,
        "case_id": "M8_TEST_RANK_VS_RETURN",
        "decision_at_utc": DECISION_AT,
        "ruleset_id": RULES["ruleset_id"],
        "universe_version": UNIVERSE["snapshot_id"],
        "transaction_cost_model_sha256": COST_SHA,
        "m7_result_sha256": None,
        "tournament_state": {
            "subject_competitor_id": "subject",
            "current_capital_actipesos": 1_000_000,
            "sessions_remaining": 5,
            "total_sessions": 20,
            "leaderboard_snapshot": {
                "as_of_utc": "2026-10-05T19:50:00Z",
                "complete": True,
                "competitors": [{"competitor_id": "leader", "current_capital_actipesos": 1_100_000}],
            },
        },
        "portfolio_state": {
            "cash_actipesos": 0,
            "holdings": [
                {"instrument_id": instrument_id, "market_value_actipesos": 200_000}
                for instrument_id in ids
            ],
            "traded_instrument_ids": ids,
            "cumulative_purchase_value_actipesos_by_instrument": {
                instrument_id: 200_000 for instrument_id in ids
            },
        },
        "ruin_floor_actipesos": 100_000,
        "evidence": {
            "sample_type": "synthetic_fixture",
            "alpha_source_available_at_utc": "2026-10-05T19:00:00Z",
            "scenario_source_available_at_utc": "2026-10-05T19:00:00Z",
            "leaderboard_source_available_at_utc": "2026-10-05T19:45:00Z",
            "final_holdout_locked": True,
            "source_manifest_sha256": None,
        },
        "scenario_models": [_model("base"), _model("aggressive_leader", 0.3)],
        "optimizer": {
            "seed": 17,
            "candidate_count": 20,
            "max_active_positions": 5,
            "holdout_draws": 1000,
            "late_stage_fraction": 0.3,
            "defend_p1_tolerance": 0.02,
            "catch_up_p1_tolerance": 0.02,
        },
        "candidate_portfolios": [],
    }


def m7_result(case: dict) -> dict:
    ids = [item["instrument_id"] for item in _assets()]
    return {
        "schema_version": 1,
        "software_status": "PASS",
        "forecast_status": "CALIBRATED",
        "empirical_gate": "NEEDS_MORE_EVIDENCE",
        "input_trace": {
            "verified_universe_version": case["universe_version"],
            "transaction_cost_model_sha256": COST_SHA,
        },
        "predictions": [
            {
                "split": "live",
                "forecast_status": "CALIBRATED_OOS_MODEL",
                "decision_at_utc": DECISION_AT,
                "instrument_id": instrument_id,
                "horizon_sessions": 5,
                "distribution": {"q05": -0.8, "q50": 0.04, "q95": 0.8},
            }
            for instrument_id in ids
        ],
    }


def _bound_inputs(case: dict) -> tuple[dict, str]:
    forecast = m7_result(case)
    raw = (json.dumps(forecast, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    case["m7_result_sha256"] = digest
    return forecast, digest


class TournamentEngineTests(unittest.TestCase):
    def test_compares_rank_aware_against_expected_return_and_sharpe(self):
        case = tournament_case()
        forecast, digest = _bound_inputs(case)
        result = evaluate_tournament(
            case, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE
        )

        self.assertEqual(result["decision_status"], "SIMULATION_ONLY")
        self.assertEqual(result["empirical_gate"], "NEEDS_MORE_EVIDENCE")
        self.assertIsNone(result["decision"])
        self.assertEqual(result["mode"]["value"], "CATCH_UP")
        self.assertEqual(len(result["comparisons"]), 3)
        by_strategy = {row["strategy"]: row["holdout"] for row in result["comparisons"]}
        rank = by_strategy["rank_aware"]
        expected = by_strategy["expected_return"]
        self.assertGreater(rank["unique_first_probability"], expected["unique_first_probability"])
        self.assertLess(rank["expected_net_return"], expected["expected_net_return"])
        self.assertIn("pese a menor retorno esperado", result["rank_aware_vs_expected_return"]["explanation"])
        self.assertGreater(result["candidate_search"]["generated_candidate_count"], 20)
        self.assertTrue(result["candidate_search"]["holdout_used_for_selection"] is False)
        self.assertEqual(len(result["leaderboard_sensitivity"]), 2)
        self.assertTrue(all(row["m1_constraints"]["constraint_status"] == "PASS" for row in result["comparisons"]))

    def test_missing_m7_and_incomplete_leaderboard_fail_closed(self):
        case = tournament_case()
        forecast, digest = _bound_inputs(case)
        no_forecast = evaluate_tournament(
            case, None, m7_result_sha256=None, ruleset=RULES, universe=UNIVERSE
        )
        self.assertEqual(no_forecast["decision_status"], "NO_DECISION")
        self.assertIsNone(no_forecast["decision"])

        case["tournament_state"]["leaderboard_snapshot"]["complete"] = False
        incomplete = evaluate_tournament(
            case, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE
        )
        self.assertEqual(incomplete["decision_status"], "NO_DECISION")

        case["tournament_state"]["leaderboard_snapshot"]["complete"] = True
        empty_m7 = deepcopy(forecast)
        empty_m7["forecast_status"] = "NO_PROMOTED_SIGNALS"
        empty_m7["predictions"] = []
        no_promotions = evaluate_tournament(
            case, empty_m7, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE
        )
        self.assertEqual(no_promotions["forecast_status"], "NO_PROMOTED_SIGNALS")
        self.assertEqual(no_promotions["decision_status"], "NO_DECISION")

    def test_m7_digest_and_future_source_cutoffs_are_rejected(self):
        case = tournament_case()
        forecast, digest = _bound_inputs(case)
        with self.assertRaisesRegex(TournamentError, "SHA-256 does not match"):
            evaluate_tournament(case, forecast, m7_result_sha256="0" * 64, ruleset=RULES, universe=UNIVERSE)

        future = deepcopy(case)
        future["evidence"]["scenario_source_available_at_utc"] = "2026-10-05T19:40:00Z"
        with self.assertRaisesRegex(TournamentError, "scenario source was not available"):
            evaluate_tournament(future, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE)

    def test_subject_cannot_be_counted_as_a_rival_and_holdout_must_be_locked(self):
        case = tournament_case()
        forecast, digest = _bound_inputs(case)
        case["tournament_state"]["leaderboard_snapshot"]["competitors"].append(
            {"competitor_id": "subject", "current_capital_actipesos": 1_000_000}
        )
        with self.assertRaisesRegex(TournamentError, "must exclude the subject"):
            evaluate_tournament(case, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE)

        case = tournament_case()
        case["evidence"]["final_holdout_locked"] = False
        with self.assertRaisesRegex(TournamentError, "locked holdout"):
            evaluate_tournament(case, None, m7_result_sha256=None, ruleset=RULES, universe=UNIVERSE)

    def test_optimizer_is_deterministic_and_holdout_does_not_select(self):
        case = tournament_case()
        forecast, digest = _bound_inputs(case)
        first = evaluate_tournament(case, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE)
        second = evaluate_tournament(case, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE)
        self.assertEqual(first, second)

        changed_holdout = deepcopy(case)
        for scenario in changed_holdout["scenario_models"][0]["holdout_scenarios"]:
            scenario["competitor_returns"]["leader"] = 0.5
        changed = evaluate_tournament(
            changed_holdout, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE
        )
        self.assertEqual(first["selection"], changed["selection"])

    def test_candidate_with_too_few_shares_is_reported_as_rejected(self):
        case = tournament_case()
        ids = [item["instrument_id"] for item in _assets()]
        case["candidate_portfolios"] = [
            {"candidate_id": "four_shares", "weights": {key: 0.25 for key in ids[:4]}}
        ]
        forecast, digest = _bound_inputs(case)
        result = evaluate_tournament(case, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE)
        rejection = next(row for row in result["candidate_search"]["rejections"] if row["candidate_id"] == "four_shares")
        self.assertTrue(any(check.get("check_id") == "minimum_five_equity_positions" for check in rejection["constraints"]["checks"]))

    def test_leader_mode_and_resource_limits_are_explicit(self):
        case = tournament_case()
        case["tournament_state"]["current_capital_actipesos"] = 1_200_000
        for holding in case["portfolio_state"]["holdings"]:
            holding["market_value_actipesos"] = 240_000
        forecast, digest = _bound_inputs(case)
        result = evaluate_tournament(case, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE)
        self.assertEqual(result["mode"]["value"], "DEFEND")

        expensive = deepcopy(case)
        expensive["optimizer"]["max_active_positions"] = 207
        expensive["optimizer"]["holdout_draws"] = 100_000
        with self.assertRaisesRegex(TournamentError, "30-million portfolio-scenario work budget"):
            evaluate_tournament(expensive, forecast, m7_result_sha256=digest, ruleset=RULES, universe=UNIVERSE)

    def test_duplicate_traded_ids_and_unknown_portfolio_ids_are_rejected(self):
        case = tournament_case()
        case["portfolio_state"]["traded_instrument_ids"].append(
            case["portfolio_state"]["traded_instrument_ids"][0]
        )
        with self.assertRaisesRegex(TournamentError, "must not contain duplicates"):
            evaluate_tournament(case, None, m7_result_sha256=None, ruleset=RULES, universe=UNIVERSE)

        case = tournament_case()
        case["portfolio_state"]["traded_instrument_ids"][0] = "unknown:asset"
        with self.assertRaisesRegex(TournamentError, "outside the verified M1 universe"):
            evaluate_tournament(case, None, m7_result_sha256=None, ruleset=RULES, universe=UNIVERSE)


class TournamentCliTests(unittest.TestCase):
    def test_cli_emits_no_decision_without_m7_and_finds_root_from_nested_cwd(self):
        self.assertEqual(_repository_root(ROOT / "tests" / "nested", Path(__file__)), ROOT)
        case = tournament_case()
        with tempfile.TemporaryDirectory() as directory:
            case_path = Path(directory) / "case.json"
            case_path.write_text(json.dumps(case), encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                status = tournament_main(["evaluate", "--case", str(case_path)])
        result = json.loads(stdout.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(result["decision_status"], "NO_DECISION")
        self.assertIsNone(result["decision"])

    def test_cli_binds_exact_m7_file_bytes_and_outputs_simulation(self):
        case = tournament_case()
        forecast = m7_result(case)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            forecast_path = folder / "m7.json"
            forecast_path.write_text(json.dumps(forecast, indent=2), encoding="utf-8")
            case["m7_result_sha256"] = hashlib.sha256(forecast_path.read_bytes()).hexdigest()
            case_path = folder / "case.json"
            case_path.write_text(json.dumps(case, indent=2), encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                status = tournament_main([
                    "evaluate", "--case", str(case_path), "--m7-result", str(forecast_path)
                ])
        result = json.loads(stdout.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(result["decision_status"], "SIMULATION_ONLY")
        self.assertIsNone(result["decision"])

    def test_phase_schemas_are_valid_json_and_forbid_order_decisions(self):
        case_schema = json.loads((ROOT / "schemas/tournament_case.schema.json").read_text(encoding="utf-8"))
        result_schema = json.loads((ROOT / "schemas/tournament_result.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(case_schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(result_schema["properties"]["decision"]["type"], "null")
        self.assertEqual(result_schema["properties"]["empirical_gate"]["const"], "NEEDS_MORE_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
