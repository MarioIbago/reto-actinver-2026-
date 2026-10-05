from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from actinver.ensemble import EnsembleError, evaluate_ensemble, forecast_artifact_sha256
from actinver.ensemble_cli import _repository_root, main as ensemble_main
from actinver.m1 import load_universe


ROOT = Path(__file__).resolve().parents[1]
DATASET_SHA = hashlib.sha256(b"synthetic M7 fixture dataset").hexdigest()
PROMOTION_A = "a" * 64
PROMOTION_B = "b" * 64
COST_MODEL = {"commission_and_iva_per_side": "0.00116", "slippage_bps_per_side": 5}
COST_MODEL_SHA = hashlib.sha256(
    (json.dumps(COST_MODEL, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
).hexdigest()


def promotion_index(case=None):
    case = case or ensemble_case()

    def item(experiment_id, hypothesis_id, family, feature, digest, signal_id):
        artifact_sha = forecast_artifact_sha256(case, signal_id)
        return {
            "experiment_id": experiment_id,
            "hypothesis_id": hypothesis_id,
            "promotion_record_sha256": digest,
            "scientific_decision": "PROMOTE",
            "m5_gate_downgraded": False,
            "experiment_spec": {
                "experiment_id": experiment_id,
                "strategy_family": family,
                "features": [feature],
                "dataset_version": "m7-synthetic-fixture-v1",
                "universe_version": "m1-synthetic-universe-v1",
                "target": "instrument_forward_return_net_of_costs",
                "horizon": "3 sessions",
                "transaction_cost_model": COST_MODEL,
                "evidence": {
                    "data_status": "authorized_point_in_time",
                    "source_availability_verified": True,
                    "instrument_mapping_verified": True,
                    "m3_execution_evidence_verified": True,
                    "costs_verified": True,
                    "dataset_manifest_sha256": DATASET_SHA,
                    "final_holdout_locked": True,
                    "test_used_for_selection": False,
                    "m3_result_sha256": "e" * 64,
                },
            },
            "validation_result": {
                "instrument_forecast_artifact": {
                    "schema_version": 1,
                    "forecast_artifact_sha256": artifact_sha,
                    "dataset_id": "m7-synthetic-fixture-v1",
                    "dataset_sha256": DATASET_SHA,
                    "universe_version": "m1-synthetic-universe-v1",
                    "target": "instrument_forward_return_net_of_costs",
                    "transaction_cost_model_sha256": COST_MODEL_SHA,
                    "horizon": "3 sessions",
                    "horizon_sessions": 3,
                }
            },
        }

    return {
        "status": "PASS",
        "ledger_head_record_sha256": "c" * 64,
        "promoted_experiments": [
            item("EXP_MOM", "HYP_MOM", "momentum", "mom_20", PROMOTION_A, "momentum-v1"),
            item("EXP_EVENT", "HYP_EVENT", "quantified_event", "event_surprise", PROMOTION_B, "event-v1"),
        ],
    }


def registry(case=None):
    case = case or ensemble_case()
    return {
        "schema_version": 1,
        "registry_id": "m7-test-registry",
        "signals": [
            {
                "signal_id": "momentum-v1",
                "experiment_id": "EXP_MOM",
                "hypothesis_id": "HYP_MOM",
                "promotion_record_sha256": PROMOTION_A,
                "family_id": "momentum",
                "source_type": "deterministic",
                "feature_ids": ["mom_20"],
                "dataset_id": "m7-synthetic-fixture-v1",
                "dataset_sha256": DATASET_SHA,
                "universe_version": "m1-synthetic-universe-v1",
                "target": "instrument_forward_return_net_of_costs",
                "transaction_cost_model_sha256": COST_MODEL_SHA,
                "forecast_artifact_sha256": forecast_artifact_sha256(case, "momentum-v1"),
                "horizon": "3 sessions",
                "horizon_sessions": 3,
            },
            {
                "signal_id": "event-v1",
                "experiment_id": "EXP_EVENT",
                "hypothesis_id": "HYP_EVENT",
                "promotion_record_sha256": PROMOTION_B,
                "family_id": "quantified_event",
                "source_type": "quantified_event",
                "feature_ids": ["event_surprise"],
                "dataset_id": "m7-synthetic-fixture-v1",
                "dataset_sha256": DATASET_SHA,
                "universe_version": "m1-synthetic-universe-v1",
                "target": "instrument_forward_return_net_of_costs",
                "transaction_cost_model_sha256": COST_MODEL_SHA,
                "forecast_artifact_sha256": forecast_artifact_sha256(case, "event-v1"),
                "horizon": "3 sessions",
                "horizon_sessions": 3,
            },
        ],
    }


def _timestamp(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def ensemble_case():
    rows = []
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    phases = (("train", 40), ("validation", 40), ("test", 40), ("live", 1))
    offset = 0
    for split, count in phases:
        for day in range(count):
            decision = start + timedelta(days=offset + day)
            for instrument_index, instrument_id in enumerate(("MX:ONE", "MX:TWO", "US:THREE")):
                move = (instrument_index - 1) * (1 + ((day + offset) % 5) * 0.1)
                return_value = (0.001 if (day + instrument_index) % 2 == 0 else -0.0006) + instrument_index * 0.00005
                if split == "live":
                    actual = None
                else:
                    actual = return_value
                rotated = ((instrument_index + day) % 3 - 1) * 0.8
                forecasts = [
                    {
                        "signal_id": "momentum-v1",
                        "available_at_utc": _timestamp(decision - timedelta(minutes=5)),
                        "raw_score": move,
                        "q05": -0.004 + move * 0.0001,
                        "q25": -0.0015 + move * 0.0001,
                        "q50": 0.0001 + move * 0.0001,
                        "q75": 0.0018 + move * 0.0001,
                        "q95": 0.004 + move * 0.0001,
                        "p_positive": 0.8 if return_value > 0 else 0.2,
                    },
                    {
                        "signal_id": "event-v1",
                        "available_at_utc": _timestamp(decision - timedelta(minutes=3)),
                        "raw_score": rotated,
                        "q05": -0.005 + rotated * 0.0002,
                        "q25": -0.002 + rotated * 0.0002,
                        "q50": -0.0001 + rotated * 0.0002,
                        "q75": 0.002 + rotated * 0.0002,
                        "q95": 0.005 + rotated * 0.0002,
                        "p_positive": 0.75 if return_value > 0 else 0.25,
                    },
                ]
                rows.append({
                    "observation_id": f"{split}-{day}-{instrument_id}",
                    "instrument_id": instrument_id,
                    "horizon_sessions": 3,
                    "decision_at_utc": _timestamp(decision),
                    "target_end_at_utc": _timestamp(decision + timedelta(hours=2)),
                    "split": split,
                    "regime": "volatile" if (day + offset) % 2 else "calm",
                    "regime_available_at_utc": _timestamp(decision - timedelta(minutes=1)),
                    "realized_return": actual,
                    "forecasts": forecasts,
                })
        offset += count
    return {
        "schema_version": 1,
        "case_id": "m7-synthetic-mechanics-fixture",
        "dataset_id": "m7-synthetic-fixture-v1",
        "dataset_sha256": DATASET_SHA,
        "universe_version": "m1-synthetic-universe-v1",
        "target": "instrument_forward_return_net_of_costs",
        "transaction_cost_model_sha256": COST_MODEL_SHA,
        "horizon": "3 sessions",
        "horizon_sessions": 3,
        "evidence": {
            "sample_type": "synthetic_fixture",
            "source_times_verified": False,
            "instrument_mapping_verified": False,
            "execution_costs_verified": False,
            "final_holdout_locked": True,
            "source_manifest_sha256": None,
        },
        "observations": rows,
    }


class EnsembleTests(unittest.TestCase):
    def test_cli_discovers_checkout_root_from_nested_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (root / "prompts").mkdir()
            (root / "prompts" / "CURRENT_PHASE.md").write_text("M7\n", encoding="utf-8")
            nested = root / "research" / "signals"
            nested.mkdir(parents=True)

            self.assertEqual(
                _repository_root(
                    nested,
                    Path("/installed/site-packages/actinver/ensemble_cli.py"),
                ),
                root,
            )

    def test_synthetic_fixture_exercises_calibration_oos_regimes_ablation_and_live_output(self):
        case = ensemble_case()
        result = evaluate_ensemble(registry(), case, promotion_index())

        self.assertEqual(result["software_status"], "PASS")
        self.assertEqual(result["forecast_status"], "CALIBRATED")
        self.assertEqual(result["empirical_gate"], "NEEDS_MORE_EVIDENCE")
        self.assertEqual(result["oos_metrics"]["test"]["sample_count"], 120)
        self.assertEqual(result["oos_metrics"]["test"]["status"], "PASS")
        self.assertEqual(len(result["regime_diagnostics"]), 2)
        self.assertEqual(len(result["ablation"]), 2)
        live = [item for item in result["predictions"] if item["split"] == "live"]
        self.assertEqual(len(live), 3)
        self.assertTrue(all(item["believability_score"]["value"] == 0 for item in live))
        for item in result["predictions"]:
            if item["distribution"]:
                values = list(item["distribution"]["quantiles"].values())
                self.assertEqual(values, sorted(values))

    def test_test_labels_do_not_change_live_calibration_or_forecasts(self):
        case = ensemble_case()
        original = evaluate_ensemble(registry(), case, promotion_index())
        changed = ensemble_case()
        for row in changed["observations"]:
            if row["split"] == "test":
                row["realized_return"] *= -10
        updated = evaluate_ensemble(registry(), changed, promotion_index())

        def live_forecasts(result):
            return [item["distribution"] for item in result["predictions"] if item["split"] == "live"]

        self.assertEqual(live_forecasts(original), live_forecasts(updated))
        self.assertNotEqual(original["oos_metrics"]["test"], updated["oos_metrics"]["test"])

    def test_empty_registry_returns_no_promoted_signal_and_no_forecast(self):
        empty = {"schema_version": 1, "registry_id": "empty", "signals": []}
        case = ensemble_case()
        case["observations"] = []
        result = evaluate_ensemble(empty, case, {"status": "PASS", "ledger_head_record_sha256": None, "promoted_experiments": []})
        self.assertEqual(result["forecast_status"], "NO_PROMOTED_SIGNALS")
        self.assertEqual(result["predictions"], [])
        self.assertEqual(result["empirical_gate"], "NEEDS_MORE_EVIDENCE")

    def test_registry_rejects_stale_promotion_target_mismatch_and_llm_only_source(self):
        bad = registry()
        bad["signals"][0]["promotion_record_sha256"] = "d" * 64
        with self.assertRaisesRegex(EnsembleError, "current M5 promotion"):
            evaluate_ensemble(bad, ensemble_case(), promotion_index())

        bad = registry()
        bad["signals"][0]["target"] = "gross_portfolio_return"
        with self.assertRaisesRegex(EnsembleError, "instrument_forward_return_net_of_costs"):
            evaluate_ensemble(bad, ensemble_case(), promotion_index())

        bad = registry()
        bad["signals"][0]["source_type"] = "llm_only"
        with self.assertRaisesRegex(EnsembleError, "quantitative source_type"):
            evaluate_ensemble(bad, ensemble_case(), promotion_index())

        bad = registry()
        bad["signals"][0]["transaction_cost_model_sha256"] = "d" * 64
        with self.assertRaisesRegex(EnsembleError, "cost model digest"):
            evaluate_ensemble(bad, ensemble_case(), promotion_index())

    def test_m5_must_bind_per_instrument_artifact_and_case_forecasts_to_its_digest(self):
        promotions = promotion_index()
        promotions["promoted_experiments"][0]["validation_result"] = {}
        with self.assertRaisesRegex(EnsembleError, "no per-instrument forecast artifact"):
            evaluate_ensemble(registry(), ensemble_case(), promotions)

        bad_case = ensemble_case()
        bad_case["observations"][0]["forecasts"][0]["q50"] += 0.0001
        with self.assertRaisesRegex(EnsembleError, "differ from the M5-promoted artifact"):
            evaluate_ensemble(registry(), bad_case, promotion_index())

    def test_rejects_lookahead_feature_and_overlapping_time_splits(self):
        bad = ensemble_case()
        bad["observations"][0]["forecasts"][0]["available_at_utc"] = bad["observations"][0]["decision_at_utc"]
        # Equality is available at the timestamp and is admissible when the M5 artifact binds it.
        evaluate_ensemble(registry(bad), bad, promotion_index(bad))

        bad["observations"][0]["forecasts"][0]["available_at_utc"] = _timestamp(datetime(2030, 1, 1, tzinfo=timezone.utc))
        with self.assertRaisesRegex(EnsembleError, "unavailable at decision time"):
            evaluate_ensemble(registry(), bad, promotion_index())

        bad = ensemble_case()
        train_rows = [row for row in bad["observations"] if row["split"] == "train"]
        validation_start = min(row["decision_at_utc"] for row in bad["observations"] if row["split"] == "validation")
        for row in train_rows:
            row["target_end_at_utc"] = validation_start
        with self.assertRaisesRegex(EnsembleError, "labels overlap"):
            evaluate_ensemble(registry(), bad, promotion_index())

        bad = ensemble_case()
        bad["observations"][0]["regime_available_at_utc"] = _timestamp(
            datetime(2030, 1, 1, tzinfo=timezone.utc)
        )
        with self.assertRaisesRegex(EnsembleError, "regime was unavailable"):
            evaluate_ensemble(registry(), bad, promotion_index())

    def test_optional_m1_identity_gate_rejects_unknown_ids_and_universe_versions(self):
        allowed = {"MX:ONE", "MX:TWO", "US:THREE"}
        evaluate_ensemble(
            registry(), ensemble_case(), promotion_index(),
            instrument_ids=allowed,
            verified_universe_version="m1-synthetic-universe-v1",
        )
        with self.assertRaisesRegex(EnsembleError, "absent from the verified M1 universe"):
            evaluate_ensemble(
                registry(), ensemble_case(), promotion_index(),
                instrument_ids={"MX:ONE"},
                verified_universe_version="m1-synthetic-universe-v1",
            )
        with self.assertRaisesRegex(EnsembleError, "does not match the verified M1 snapshot"):
            evaluate_ensemble(
                registry(), ensemble_case(), promotion_index(),
                instrument_ids=allowed,
                verified_universe_version="different-universe-v1",
            )

    def test_cli_promotions_reports_empty_ledger_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                status = ensemble_main(["promotions", "--ledger", str(Path(directory) / "missing.jsonl")])
        self.assertEqual(status, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["promotion_count"], 0)
        self.assertEqual(result["promoted_experiments"], [])

    def test_cli_evaluate_verifies_m1_source_snapshot_with_empty_registry(self):
        universe = load_universe(ROOT / "data/metadata/actinver_universe_2026_v1.json")
        case = {
            "schema_version": 1,
            "case_id": "empty-current-state",
            "dataset_id": "synthetic-empty-fixture",
            "dataset_sha256": DATASET_SHA,
            "universe_version": universe["snapshot_id"],
            "target": "instrument_forward_return_net_of_costs",
            "transaction_cost_model_sha256": COST_MODEL_SHA,
            "horizon": "3 sessions",
            "horizon_sessions": 3,
            "evidence": {
                "sample_type": "synthetic_fixture",
                "source_times_verified": False,
                "instrument_mapping_verified": False,
                "execution_costs_verified": False,
                "final_holdout_locked": True,
                "source_manifest_sha256": None,
            },
            "observations": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            case_path = Path(directory) / "case.json"
            case_path.write_text(json.dumps(case), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                status = ensemble_main([
                    "evaluate", "--case", str(case_path), "--ledger",
                    str(Path(directory) / "missing-ledger.jsonl"),
                ])
        self.assertEqual(status, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["forecast_status"], "NO_PROMOTED_SIGNALS")
        self.assertEqual(result["input_trace"]["verified_universe_version"], universe["snapshot_id"])

    def test_all_m7_schemas_are_valid_json(self):
        for name in (
            "promoted_signal_registry.schema.json",
            "alpha_ensemble_case.schema.json",
            "alpha_ensemble_result.schema.json",
        ):
            with self.subTest(name=name):
                json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
