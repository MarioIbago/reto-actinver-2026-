import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from actinver.m1 import load_rules
from actinver.research_factory import (
    ResearchFactoryError,
    code_identity,
    register_plan,
    run_registered_batch,
    summarize_ledger,
    verify_ledger,
)
from test_validation import ROOT, validation_case


RULES = load_rules(ROOT / "config/actinver_rules.yaml")
CATEGORIES = (
    "leakage", "regime", "outliers", "parameter_sensitivity", "liquidity", "costs",
    "sample_size", "multiple_testing",
)


def write_json(path: Path, value) -> bytes:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


def reseal_ledger(path: Path, records: list[dict]) -> None:
    """Recompute the unkeyed chain so verifier tests exercise semantic checks."""
    previous = None
    lines = []
    for record in records:
        record.pop("record_sha256", None)
        record["previous_record_sha256"] = previous
        body = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        record["record_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        previous = record["record_sha256"]
        lines.append(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        )
    path.write_bytes("".join(lines).encode("utf-8"))


def hypothesis(hypothesis_id: str, statement: str) -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": hypothesis_id,
        "statement": statement,
        "rationale": "A preregistered, falsifiable software fixture checks the research lifecycle.",
        "source_references": ["local M5 test fixture"],
        "falsification_plan": [
            {
                "category": category,
                "approach": f"Run the predefined {category} diagnostic or record its explicit evidence gap.",
                "required": True,
            }
            for category in CATEGORIES
        ],
    }


def make_plan(directory: Path, *, batch_id="M5_BATCH_001", count=1, good_returns=False):
    experiments = []
    for index in range(count):
        experiment_id = f"M5_FIXTURE_{index + 1:03}"
        statement = f"Synthetic M5 fixture hypothesis {index + 1} is evaluated without financial claims."
        hyp_path = directory / f"hypothesis-{index + 1}.json"
        hyp_bytes = write_json(hyp_path, hypothesis(f"M5-HYP-{index + 1:03}", statement))
        case_path = directory / f"case-{index + 1}.json"
        case = validation_case(good_returns=good_returns and index == count - 1)
        case["experiment_id"] = experiment_id
        case["hypothesis"] = statement
        if good_returns and index == count - 1:
            case["promotion_criteria"].update(
                {
                    "minimum_test_sharpe": "-10",
                    "minimum_test_cumulative_return": "-1",
                    "minimum_improvement_vs_benchmark": "-1",
                    "minimum_dsr_probability": "0",
                    "maximum_pbo_probability": "1",
                    "maximum_test_drawdown": "1",
                }
            )
        case_bytes = write_json(case_path, case)
        experiment_spec = {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "hypothesis": statement,
            "strategy_family": "synthetic_fixture",
            "dataset_version": case["dataset_version"],
            "universe_version": case["universe_version"],
            "features": ["synthetic_return_fixture"],
            "target": "gross_portfolio_return",
            "horizon": "1 session",
            "parameters": [
                {
                    "trial_id": trial["trial_id"],
                    "parameters": trial["parameters"],
                    "parameter_sha256": trial["parameter_sha256"],
                }
                for trial in case["trials"]
            ],
            "train_period": case["train_period"],
            "validation_period": case["validation_period"],
            "test_period": case["test_period"],
            "transaction_cost_model": {
                "ruleset_id": RULES["ruleset_id"],
                "commission_rate": str(RULES["rules"]["costs"]["commission_rate"]),
                "iva_rate_on_commission": str(RULES["rules"]["costs"]["iva_rate_on_commission"]),
                "slippage_bps_per_side": case["cost_sensitivity_bps"],
                "turnover_definition": "total absolute traded notional divided by prior portfolio value",
            },
            "execution_model": "synthetic_m3_return_fixture",
            "benchmark_trial_id": case["benchmark_trial_id"],
            "promotion_criteria": case["promotion_criteria"],
            "seed": case["seed"],
            "commit_sha": case["commit_sha"],
            "periods_per_year": case["periods_per_year"],
            "attempted_trial_count": case["attempted_trial_count"],
            "validation_protocol": {
                "bootstrap": case["bootstrap"],
                "walk_forward": case["walk_forward"],
                "pbo": case["pbo"],
            },
            "evidence": case["evidence"],
        }
        experiments.append(
            {
                "hypothesis_path": hyp_path.name,
                "hypothesis_sha256": hashlib.sha256(hyp_bytes).hexdigest(),
                "validation_case_path": case_path.name,
                "validation_case_sha256": hashlib.sha256(case_bytes).hexdigest(),
                "experiment_spec": experiment_spec,
            }
        )
    plan = {"schema_version": 1, "batch_id": batch_id, "experiments": experiments}
    plan_path = directory / "batch.json"
    write_json(plan_path, plan)
    return plan, plan_path


class ResearchFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.plan, self.plan_path = make_plan(self.directory, count=2, good_returns=True)
        self.ledger = self.directory / "factory_ledger.jsonl"
        self.identity = code_identity(ROOT)

    def tearDown(self):
        self.temp.cleanup()

    def register(self):
        return register_plan(
            self.plan,
            plan_path=self.plan_path,
            ledger_path=self.ledger,
            identity=self.identity,
            now_utc="2026-10-05T12:00:00Z",
        )

    def execute_batch(self):
        return run_registered_batch(
            self.plan,
            plan_path=self.plan_path,
            ledger_path=self.ledger,
            identity=self.identity,
            ruleset=RULES,
            now_utc="2026-10-05T12:01:00Z",
        )

    def test_preregistered_batch_preserves_reject_and_needs_more_evidence(self):
        with self.assertRaisesRegex(ResearchFactoryError, "preregistered"):
            self.execute_batch()
        registered = self.register()
        self.assertEqual(registered["status"], "REGISTERED")
        repeated = self.register()
        self.assertEqual(repeated["status"], "ALREADY_REGISTERED")

        result = self.execute_batch()
        self.assertEqual([item["run_status"] for item in result["results"]], ["COMPLETED", "COMPLETED"])
        self.assertEqual(result["results"][0]["scientific_decision"], "REJECT")
        self.assertEqual(result["results"][1]["scientific_decision"], "NEEDS_MORE_EVIDENCE")
        falsification = {item["category"]: item for item in result["results"][0]["falsification_checks"]}
        self.assertEqual(falsification["outliers"]["status"], "CHECKED")
        self.assertTrue(falsification["outliers"]["details"]["selection_stable"])
        self.assertEqual(falsification["outliers"]["details"]["selected_trial_after"], "candidate")
        self.assertEqual(falsification["liquidity"]["status"], "NOT_AVAILABLE")
        self.assertEqual(verify_ledger(self.ledger)["record_count"], 2)
        registered_record, result_record = [
            json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()
        ]
        snapshot = registered_record["registered_experiments"][0]["experiment_spec"]
        self.assertEqual(snapshot["parameters"][0]["parameters"]["family"], "benchmark")
        self.assertNotIn("returns", snapshot["parameters"][0])
        self.assertIn("validation_result", result_record["results"][0])
        summary = summarize_ledger(self.ledger)
        self.assertEqual(summary["hypotheses_registered"], 2)
        self.assertEqual(summary["hypotheses_tested"], 2)
        self.assertEqual(summary["experiments_completed"], 2)
        self.assertEqual(summary["decision_attempt_counts"]["REJECT"], 1)
        self.assertEqual(summary["decision_attempt_counts"]["NEEDS_MORE_EVIDENCE"], 1)
        self.assertEqual(summary["decision_attempt_counts"]["PROMOTE"], 0)

    def test_changed_case_is_preserved_as_a_run_error(self):
        self.register()
        case_path = self.directory / self.plan["experiments"][0]["validation_case_path"]
        case_path.write_text("{}\n", encoding="utf-8")
        result = self.execute_batch()
        self.assertEqual(result["results"][0]["run_status"], "RUN_ERROR")
        self.assertIn("fingerprint changed", result["results"][0]["error"])
        summary = summarize_ledger(self.ledger)
        self.assertEqual(summary["run_errors"], 1)
        self.assertEqual(summary["decision_attempt_counts"]["NEEDS_MORE_EVIDENCE"], 2)
        self.assertEqual(verify_ledger(self.ledger)["status"], "PASS")

    def test_invalid_parameter_fingerprint_fails_before_ledger_append(self):
        plan, plan_path = make_plan(self.directory, batch_id="M5_BAD_HASH", count=1)
        case_path = self.directory / plan["experiments"][0]["validation_case_path"]
        case = json.loads(case_path.read_text(encoding="utf-8"))
        case["trials"][0]["parameter_sha256"] = "0" * 64
        case_bytes = write_json(case_path, case)
        plan["experiments"][0]["validation_case_sha256"] = hashlib.sha256(case_bytes).hexdigest()
        write_json(plan_path, plan)
        ledger = self.directory / "bad-hash-ledger.jsonl"
        with self.assertRaisesRegex(ResearchFactoryError, "parameter fingerprint does not match"):
            register_plan(
                plan,
                plan_path=plan_path,
                ledger_path=ledger,
                identity=self.identity,
                now_utc="2026-10-05T12:00:00Z",
            )
        self.assertFalse(ledger.exists())

    def test_non_chronological_experiment_spec_fails_before_registration(self):
        plan, plan_path = make_plan(self.directory, batch_id="M5_BAD_PERIODS", count=1)
        spec = plan["experiments"][0]["experiment_spec"]
        spec["validation_period"]["start"] = spec["train_period"]["end"]
        ledger = self.directory / "bad-period-ledger.jsonl"
        with self.assertRaisesRegex(ResearchFactoryError, "chronological and non-overlapping"):
            register_plan(
                plan,
                plan_path=plan_path,
                ledger_path=ledger,
                identity=self.identity,
                now_utc="2026-10-05T12:00:00Z",
            )
        self.assertFalse(ledger.exists())

    def test_registered_code_identity_is_locked_and_completed_batch_is_immutable(self):
        self.register()
        changed_identity = dict(self.identity, code_tree_sha256="f" * 64)
        with self.assertRaisesRegex(ResearchFactoryError, "code identity changed"):
            run_registered_batch(
                self.plan,
                plan_path=self.plan_path,
                ledger_path=self.ledger,
                identity=changed_identity,
                ruleset=RULES,
            )
        self.execute_batch()
        with self.assertRaisesRegex(ResearchFactoryError, "already has a completed"):
            self.execute_batch()

    def test_ledger_detects_tampering(self):
        self.register()
        self.execute_batch()
        content = self.ledger.read_bytes()
        self.ledger.write_bytes(content.replace(b"M5_BATCH_001", b"M5_BATCH_002", 1))
        with self.assertRaisesRegex(ResearchFactoryError, "fingerprint mismatch"):
            verify_ledger(self.ledger)

    def test_ledger_rejects_resealed_registration_snapshot_that_differs_from_plan(self):
        self.register()
        self.execute_batch()
        records = [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]
        records[0]["registered_experiments"][0]["experiment_spec"]["strategy_family"] = "changed-after-registration"
        reseal_ledger(self.ledger, records)
        with self.assertRaisesRegex(ResearchFactoryError, "ExperimentSpec does not match its plan"):
            verify_ledger(self.ledger)

    def test_ledger_rejects_result_disconnected_from_registered_hypothesis(self):
        self.register()
        self.execute_batch()
        records = [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]
        records[1]["results"][0]["hypothesis_id"] = "different-hypothesis"
        reseal_ledger(self.ledger, records)
        with self.assertRaisesRegex(ResearchFactoryError, "result hypothesis does not match preregistration"):
            verify_ledger(self.ledger)

    def test_plan_and_result_schemas_parse_and_cli_runs_installed_batch(self):
        for name in (
            "research_hypothesis.schema.json",
            "research_plan.schema.json",
            "research_experiment_spec.schema.json",
            "research_ledger_record.schema.json",
        ):
            schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        cli = shutil.which("actinver-research")
        self.assertIsNotNone(cli, "actinver-research console script must be installed")
        self.assertEqual(self.register()["status"], "REGISTERED")
        self.execute_batch()
        record_schema = json.loads(
            (ROOT / "schemas/research_ledger_record.schema.json").read_text(encoding="utf-8")
        )
        for raw_line in self.ledger.read_text(encoding="utf-8").splitlines():
            record = json.loads(raw_line)
            self.assertTrue(set(record_schema["required"]).issubset(record))
            self.assertFalse(set(record) - set(record_schema["properties"]))
        result_schema = record_schema["$defs"]["experimentResult"]
        self.assertTrue(result_schema["required"])
        # Exercise the public command in an independent process using a fresh ledger.
        second_plan, second_plan_path = make_plan(self.directory, batch_id="M5_CLI_BATCH", count=1)
        second_ledger = self.directory / "cli-ledger.jsonl"
        command_base = [cli]
        registered = subprocess.run(
            command_base + ["register", "--plan", str(second_plan_path), "--ledger", str(second_ledger)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(registered.returncode, 0, registered.stderr)
        executed = subprocess.run(
            command_base + ["run-batch", "--plan", str(second_plan_path), "--ledger", str(second_ledger)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        summary = subprocess.run(
            command_base + ["summary", "--ledger", str(second_ledger)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(summary.returncode, 0, summary.stderr)
        self.assertEqual(json.loads(summary.stdout)["hypotheses_tested"], 1)


if __name__ == "__main__":
    unittest.main()
