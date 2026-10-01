import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from actinver.contracts import ExperimentResult, ExperimentSpec, canonical_json, load_json
from actinver.smoke import run_smoke


SPEC_PATH = Path(__file__).resolve().parents[1] / "experiments/specs/HARNESS_SMOKE_001.json"


def make_spec() -> ExperimentSpec:
    return ExperimentSpec.from_dict(load_json(SPEC_PATH))


def metadata(commit=None) -> dict:
    return {"commit_sha": commit, "working_tree_dirty": None,
            "python_version": "3.11.0", "package_version": "0.1.0",
            "timestamp_utc": "2026-01-01T00:00:00+00:00", "run_id": None}


def make_result() -> ExperimentResult:
    return run_smoke(make_spec(), metadata())


class ContractTests(unittest.TestCase):
    def test_required_spec_fields(self):
        original = load_json(SPEC_PATH)
        for name in original:
            with self.subTest(field=name):
                value = copy.deepcopy(original)
                del value[name]
                with self.assertRaises(ValueError):
                    ExperimentSpec.from_dict(value)

    def test_required_result_fields(self):
        original = make_result().to_dict()
        mandatory = ("schema_version", "experiment_id", "dataset_version", "universe_version",
                     "seed", "config_sha256", "code_sha256", "status", "values", "metrics",
                     "failure_reason")
        for name in mandatory:
            with self.subTest(field=name):
                value = copy.deepcopy(original)
                del value["payload"][name]
                with self.assertRaises(ValueError):
                    ExperimentResult.from_dict(value)
        for name in ("payload", "execution"):
            value = copy.deepcopy(original)
            del value[name]
            with self.assertRaises(ValueError):
                ExperimentResult.from_dict(value)

    def test_spec_types_and_values(self):
        changes = [{"schema_version": True}, {"schema_version": 2},
                   {"experiment_id": "OTHER"}, {"hypothesis": " "}, {"seed": True},
                   {"seed": -1}, {"seed": 42.0}, {"commit_sha": "short"},
                   {"parameters": {"sample_count": 0, "modulus": 101}},
                   {"parameters": {"sample_count": 65, "modulus": 101}},
                   {"parameters": {"sample_count": 8, "modulus": True}},
                   {"benchmark": {"expected_values": [43]}},
                   {"features": ["unexpected"]}, {"universe_version": "raw"},
                   {"extra": None}]
        for change in changes:
            with self.subTest(change=change):
                value = make_spec().to_dict()
                value.update(change)
                with self.assertRaises(ValueError):
                    ExperimentSpec.from_dict(value)

    def test_result_types_and_values(self):
        changes = [{"schema_version": True}, {"seed": False}, {"status": "OTHER"},
                   {"config_sha256": "bad"}, {"code_sha256": "bad"},
                   {"values": [True]}, {"failure_reason": "unexpected"},
                   {"promotion_status": "unexpected"}, {"turnover": 0},
                   {"extra": 1}]
        for change in changes:
            with self.subTest(change=change):
                value = make_result().to_dict()
                value["payload"].update(change)
                with self.assertRaises(ValueError):
                    ExperimentResult.from_dict(value)
        for change in ({"commit_sha": 1}, {"timestamp_utc": "2026-01-01T00:00:00"},
                       {"working_tree_dirty": "false"}, {"run_id": 123},
                       {"python_version": ""}):
            with self.subTest(change=change):
                value = make_result().to_dict()
                value["execution"].update(change)
                with self.assertRaises(ValueError):
                    ExperimentResult.from_dict(value)

    def test_canonical_json_and_round_trip(self):
        expected = '{"a":[1,true,null],"b":"é"}\n'.encode("utf-8")
        self.assertEqual(canonical_json({"b": "é", "a": [1, True, None]}), expected)
        self.assertEqual(canonical_json({"a": [1, True, None], "b": "é"}), expected)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            result = make_result()
            path.write_bytes(canonical_json(result.to_dict()))
            restored = ExperimentResult.from_dict(load_json(path))
            self.assertEqual(restored, result)

    def test_reject_nonfinite_numbers_and_non_json_values(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_json({"nested": [value]})
        for value in ({1: "not a string key"}, {"tuple": (1, 2)}, {"set": {1}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_json(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for text in ('{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}',
                         '{"x":1e400}', '{"x":1,"x":2}'):
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_json(path)

    def test_config_hash_is_semantic_and_excludes_commit(self):
        spec = make_spec()
        reversed_order = dict(reversed(list(spec.to_dict().items())))
        reversed_order["parameters"] = dict(reversed(list(spec.parameters.items())))
        self.assertEqual(spec.config_sha256, ExperimentSpec.from_dict(reversed_order).config_sha256)
        self.assertEqual(spec.config_sha256, replace(spec, commit_sha="a" * 40).config_sha256)
        self.assertNotEqual(spec.config_sha256, replace(spec, seed=43).config_sha256)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            path.write_bytes(canonical_json(spec.to_dict()))
            self.assertEqual(spec.config_sha256, ExperimentSpec.from_dict(load_json(path)).config_sha256)


if __name__ == "__main__":
    unittest.main()
