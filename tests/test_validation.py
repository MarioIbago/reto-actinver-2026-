from datetime import date, timedelta
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from actinver.m1 import load_rules
from actinver.validation import ValidationError, evaluate_validation_case


ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(ROOT / "config/actinver_rules.yaml")


def weekdays(start: date, count: int) -> list[date]:
    result = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def validation_case(*, data_status="synthetic_fixture", good_returns=False, test_used_for_selection=False):
    days = weekdays(date(2025, 1, 1), 100)
    train = days[:40]
    validation = days[40:70]
    test = days[70:]
    noise = ["-0.0004", "0.0001", "0.0005", "-0.0001", "0.0003"]
    trials = []
    for trial_id, parameters in (
        ("benchmark", {"family": "benchmark", "lookback_sessions": 10}),
        ("candidate", {"family": "momentum", "lookback_sessions": 20}),
    ):
        rows = []
        for index, day in enumerate(days):
            perturbation = float(noise[index % len(noise)])
            if trial_id == "benchmark" or good_returns:
                gross = 0.0007 + perturbation
            elif index < 70:
                gross = 0.003 + perturbation
            else:
                gross = -0.001 + perturbation
            rows.append(
                {
                    "date": day.isoformat(),
                    "gross_return": f"{gross:.8f}",
                    "turnover": "0.2",
                    "regime": "bull" if index < 70 else "bear",
                }
            )
        parameter_bytes = (
            json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        trials.append(
            {
                "trial_id": trial_id,
                "parameters": parameters,
                "parameter_sha256": hashlib.sha256(parameter_bytes).hexdigest(),
                "returns": rows,
            }
        )
    return {
        "schema_version": 1,
        "experiment_id": "M4_VALIDATION_FIXTURE_001",
        "hypothesis": "A preregistered return stream is evaluated by a time-aware pipeline.",
        "dataset_version": "synthetic-validation-fixture-v1",
        "universe_version": "guide-universe-fixture-v1",
        "commit_sha": None,
        "seed": 19,
        "periods_per_year": 252,
        "evidence": {
            "data_status": data_status,
            "source_availability_verified": False,
            "instrument_mapping_verified": False,
            "m3_execution_evidence_verified": False,
            "costs_verified": False,
            "final_holdout_locked": True,
            "test_used_for_selection": test_used_for_selection,
            "dataset_manifest_sha256": None,
            "m3_result_sha256": None,
        },
        "train_period": {"start": train[0].isoformat(), "end": train[-1].isoformat()},
        "validation_period": {"start": validation[0].isoformat(), "end": validation[-1].isoformat()},
        "test_period": {"start": test[0].isoformat(), "end": test[-1].isoformat()},
        "bootstrap": {"iterations": 120, "block_length": 4, "confidence_level": "0.95"},
        "walk_forward": {
            "mode": "expanding",
            "train_sessions": 20,
            "evaluation_sessions": 10,
            "step_sessions": 10,
        },
        "pbo": {"blocks": 8},
        "cost_sensitivity_bps": ["0", "5", "10"],
        "benchmark_trial_id": "benchmark",
        "attempted_trial_count": 4,
        "promotion_criteria": {
            "minimum_test_sessions": 20,
            "minimum_test_sharpe": "0",
            "minimum_test_cumulative_return": "0",
            "minimum_improvement_vs_benchmark": "0",
            "minimum_dsr_probability": "0.95",
            "maximum_pbo_probability": "0.20",
            "maximum_test_drawdown": "0.30",
        },
        "trials": trials,
    }


class ValidationEngineTests(unittest.TestCase):
    def test_overfit_candidate_is_selected_on_validation_and_rejected_on_holdout(self):
        result = evaluate_validation_case(validation_case(), RULES)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["selected_trial_id"], "candidate")
        self.assertEqual(result["status_decision"], "REJECT")
        self.assertLess(result["metrics"]["selected_trial"]["test"]["cumulative_return"], 0)
        self.assertTrue(any("test cumulative return" in reason for reason in result["decision_reasons"]))
        self.assertFalse(result["multiple_testing_context"]["final_test_used_for_selection"])

    def test_synthetic_winning_baseline_never_promotes(self):
        value = validation_case(good_returns=True)
        value["promotion_criteria"].update(
            {
                "minimum_test_sessions": 20,
                "minimum_test_sharpe": "-10",
                "minimum_test_cumulative_return": "-1",
                "minimum_improvement_vs_benchmark": "-1",
                "minimum_dsr_probability": "0",
                "maximum_pbo_probability": "1",
                "maximum_test_drawdown": "1",
            }
        )
        result = evaluate_validation_case(value, RULES)
        self.assertEqual(result["status_decision"], "NEEDS_MORE_EVIDENCE")
        self.assertTrue(any("authorized point-in-time" in gap for gap in result["evidence_gaps"]))

    def test_final_holdout_used_for_selection_is_rejected(self):
        result = evaluate_validation_case(validation_case(test_used_for_selection=True), RULES)
        self.assertEqual(result["status_decision"], "REJECT")
        self.assertIn("final holdout was used for trial selection", result["decision_reasons"])

    def test_walk_forward_bootstrap_pbo_and_dsr_are_reproducible(self):
        case = validation_case()
        first = evaluate_validation_case(case, RULES)
        second = evaluate_validation_case(copy.deepcopy(case), RULES)
        self.assertEqual(first, second)
        self.assertEqual(first["walk_forward"]["status"], "PASS")
        self.assertGreater(first["walk_forward"]["fold_count"], 0)
        test_start = case["test_period"]["start"]
        self.assertTrue(all(fold["evaluation_end"] < test_start for fold in first["walk_forward"]["folds"]))
        self.assertFalse(first["walk_forward"]["final_test_period_used"])
        self.assertEqual(first["bootstrap"]["status"], "PASS")
        self.assertEqual(first["pbo"]["status"], "PASS")
        self.assertEqual(first["deflated_sharpe_ratio"]["status"], "PASS")

    def test_parameter_sensitivity_is_reported_and_hashes_are_verified(self):
        case = validation_case()
        result = evaluate_validation_case(case, RULES)
        lookback = result["parameter_sensitivity"]["parameters"]["lookback_sessions"]
        self.assertEqual(lookback["value_groups"]["10"]["trial_count"], 1)
        self.assertEqual(lookback["value_groups"]["20"]["trial_count"], 1)
        self.assertIsNotNone(lookback["validation_sharpe_range"])

        case["trials"][1]["parameter_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValidationError, "does not match its parameters"):
            evaluate_validation_case(case, RULES)

    def test_dsr_selection_threshold_includes_the_trial_sharpe_mean(self):
        result = evaluate_validation_case(validation_case(good_returns=True), RULES)
        dsr = result["deflated_sharpe_ratio"]
        self.assertAlmostEqual(
            dsr["expected_max_sharpe_threshold_per_period"],
            dsr["selected_validation_sharpe_per_period"],
            places=10,
        )

    def test_cost_sensitivity_increases_drag_without_reselecting_the_trial(self):
        result = evaluate_validation_case(validation_case(), RULES)
        cases = result["cost_sensitivity"]
        self.assertEqual([item["slippage_bps_per_side"] for item in cases], ["0", "5", "10"])
        self.assertGreater(
            cases[0]["test_metrics"]["cumulative_return"],
            cases[1]["test_metrics"]["cumulative_return"],
        )
        self.assertGreater(
            cases[1]["test_metrics"]["cumulative_return"],
            cases[2]["test_metrics"]["cumulative_return"],
        )
        self.assertEqual(result["selected_trial_id"], "candidate")

    def test_test_returns_do_not_change_trial_selection(self):
        first = evaluate_validation_case(validation_case(), RULES)
        changed = validation_case()
        for row in changed["trials"][1]["returns"][70:]:
            row["gross_return"] = "0.50"
        second = evaluate_validation_case(changed, RULES)
        self.assertEqual(first["selected_trial_id"], second["selected_trial_id"])

    def test_rejects_overlapping_splits_unaligned_trials_and_inexact_numbers(self):
        overlap = validation_case()
        overlap["validation_period"]["start"] = overlap["train_period"]["end"]
        with self.assertRaisesRegex(ValidationError, "chronological and non-overlapping"):
            evaluate_validation_case(overlap, RULES)

        unaligned = validation_case()
        unaligned["trials"][1]["returns"].pop()
        with self.assertRaisesRegex(ValidationError, "identical, aligned return dates"):
            evaluate_validation_case(unaligned, RULES)

        float_input = validation_case()
        float_input["trials"][0]["returns"][0]["gross_return"] = 0.001
        with self.assertRaisesRegex(ValidationError, "exact decimal"):
            evaluate_validation_case(float_input, RULES)

    def test_cli_writes_hashed_provenance_and_refuses_overwrite(self):
        case = validation_case()
        installed_cli = shutil.which("actinver-m4")
        self.assertIsNotNone(installed_cli, "actinver-m4 console script must be installed")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            input_path = base / "case.json"
            output_path = base / "result.json"
            input_bytes = json.dumps(case, sort_keys=True).encode("utf-8")
            input_path.write_bytes(input_bytes)
            command = [
                installed_cli,
                "evaluate",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--code-commit-sha",
                "c" * 40,
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                result["run_provenance"]["input_sha256"], hashlib.sha256(input_bytes).hexdigest()
            )
            repeated = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 2)
            self.assertIn("Refusing to overwrite", repeated.stderr)

    def test_case_and_result_align_with_versioned_schemas(self):
        case_schema = json.loads((ROOT / "schemas/validation_case.schema.json").read_text(encoding="utf-8"))
        result_schema = json.loads((ROOT / "schemas/validation_result.schema.json").read_text(encoding="utf-8"))
        case = validation_case()
        result = evaluate_validation_case(case, RULES)
        self.assertEqual(set(case_schema["required"]), set(case))
        self.assertFalse(set(case) - set(case_schema["properties"]))
        self.assertTrue(set(result_schema["required"]).issubset(result))
        self.assertFalse(set(result) - set(result_schema["properties"]))


if __name__ == "__main__":
    unittest.main()
