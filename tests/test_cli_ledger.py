from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sysconfig
import tempfile
import unittest

from actinver.contracts import canonical_json, load_json
from actinver.ledger import append_record
from actinver.smoke import run_smoke
from test_contracts import SPEC_PATH, make_spec, metadata


CLI = Path(sysconfig.get_path("scripts")) / "actinver-m0"


class LedgerTests(unittest.TestCase):
    def test_append_only_and_negative_results(self):
        spec = make_spec()
        result = run_smoke(spec, metadata())
        failed_spec = replace(spec, benchmark={"expected_values": [44, 46, 51, 58, 67, 78, 91, 5]})
        failed = run_smoke(failed_spec, metadata())
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            append_record(ledger, spec, result)
            first = ledger.read_bytes()
            append_record(ledger, failed_spec, failed)
            self.assertTrue(ledger.read_bytes().startswith(first))
            records = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertEqual([item["result"]["payload"]["status"] for item in records], ["PASS", "FAIL"])
            self.assertEqual(records[1]["result"]["payload"]["failure_reason"], "REFERENCE_MISMATCH")
            self.assertEqual(records[1]["spec"], failed_spec.to_dict())
            self.assertEqual(records[0]["payload_sha256"],
                             hashlib.sha256(canonical_json(result.payload)).hexdigest())

    def test_incomplete_ledger_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            prior = b'{"incomplete":'
            ledger.write_bytes(prior)
            with self.assertRaises(ValueError):
                append_record(ledger, make_spec(), run_smoke(make_spec(), metadata()))
            self.assertEqual(ledger.read_bytes(), prior)

    def test_mismatched_ledger_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            with self.assertRaises(ValueError):
                append_record(ledger, replace(make_spec(), seed=43), run_smoke(make_spec(), metadata()))
            self.assertFalse(ledger.exists())


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "run"

    def command(self, *args):
        return subprocess.run([str(CLI), *map(str, args)], cwd=self.root, text=True,
                              capture_output=True, check=False)

    def smoke(self, output=None, spec=SPEC_PATH, commit="a" * 40, run_id="first"):
        return self.command("smoke", "--spec", spec, "--output-dir", output or self.output,
                            "--commit-sha", commit, "--run-id", run_id)

    def verify(self, spec=SPEC_PATH):
        return self.command("verify", "--output-dir", self.output, "--spec", spec,
                            "--commit-sha", "a" * 40)

    def test_installed_cli_smoke_verify_and_record(self):
        completed = self.smoke()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "PASS")
        verified = self.verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("identity verified", verified.stdout)
        ledger = self.root / "permanent.jsonl"
        recorded = self.command("record", "--output-dir", self.output, "--ledger", ledger)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(len(ledger.read_text().splitlines()), 1)
        self.assertEqual({path.name for path in self.output.iterdir()},
                         {"payload.json", "result.json", "resolved_spec.json", "ledger.jsonl"})

    def test_independent_processes_and_execution_metadata(self):
        first = self.smoke()
        other = self.root / "second"
        second = self.smoke(output=other, commit="b" * 40, run_id="second")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.output / "payload.json").read_bytes(), (other / "payload.json").read_bytes())
        self.assertNotEqual((self.output / "result.json").read_bytes(), (other / "result.json").read_bytes())

    def test_valid_negative_result_is_preserved_and_recordable(self):
        changed = make_spec().to_dict()
        changed["benchmark"]["expected_values"][0] = 44
        bad_spec = self.root / "wrong-reference.json"
        bad_spec.write_bytes(canonical_json(changed))
        completed = self.smoke(spec=bad_spec)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "FAIL")
        self.assertNotEqual(self.verify(spec=bad_spec).returncode, 0)
        ledger = self.root / "negative.jsonl"
        recorded = self.command("record", "--output-dir", self.output, "--ledger", ledger)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(json.loads(ledger.read_text())["result"]["payload"]["status"], "FAIL")

    def test_missing_and_malformed_input(self):
        completed = self.smoke(spec=self.root / "absent.json")
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(self.output.exists())
        path = self.root / "bad.json"
        for content in ('{', '{"seed":NaN}', '[]'):
            path.write_text(content)
            with self.subTest(content=content):
                self.assertEqual(self.smoke(spec=path).returncode, 2)
        self.assertEqual(self.verify().returncode, 2)

    def test_existing_output_is_not_overwritten(self):
        self.assertEqual(self.smoke().returncode, 0)
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.assertEqual(self.smoke().returncode, 2)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.output.iterdir()})

    def test_verifier_rejects_missing_bundle_files(self):
        self.assertEqual(self.smoke().returncode, 0)
        for name in ("payload.json", "result.json", "resolved_spec.json"):
            with self.subTest(name=name):
                path = self.output / name
                prior = path.read_bytes()
                path.unlink()
                self.assertEqual(self.verify().returncode, 2)
                path.write_bytes(prior)

    def test_verifier_and_recorder_reject_manipulated_outputs(self):
        self.assertEqual(self.smoke().returncode, 0)
        path = self.output / "result.json"
        original = path.read_bytes()
        for field, value in (("seed", 43), ("config_sha256", "b" * 64),
                             ("code_sha256", "b" * 64)):
            with self.subTest(field=field):
                changed = json.loads(original)
                changed["payload"][field] = value
                path.write_bytes(canonical_json(changed))
                self.assertEqual(self.verify().returncode, 2)
                self.assertEqual(self.command("record", "--output-dir", self.output,
                                              "--ledger", self.root / "ledger.jsonl").returncode, 2)
        changed = json.loads(original)
        changed["payload"]["values"][0] += 1
        changed["payload"]["metrics"]["integer_sum"] += 1
        path.write_bytes(canonical_json(changed))
        self.assertEqual(self.verify().returncode, 2)
        changed = json.loads(original)
        changed["execution"]["commit_sha"] = "b" * 40
        path.write_bytes(canonical_json(changed))
        self.assertEqual(self.verify().returncode, 2)
        path.write_bytes(original)
        payload = self.output / "payload.json"
        payload.write_bytes(payload.read_bytes() + b" ")
        self.assertEqual(self.verify().returncode, 2)
        self.assertFalse((self.root / "ledger.jsonl").exists())

    def test_verifier_rejects_changed_resolved_spec(self):
        self.assertEqual(self.smoke().returncode, 0)
        path = self.output / "resolved_spec.json"
        changed = load_json(path)
        changed["seed"] = 43
        path.write_bytes(canonical_json(changed))
        self.assertEqual(self.verify().returncode, 2)


if __name__ == "__main__":
    unittest.main()
