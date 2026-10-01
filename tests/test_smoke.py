from dataclasses import replace
import random
import unittest
from unittest.mock import patch

from actinver.contracts import canonical_json
from actinver.smoke import arithmetic_values, code_sha256, run_smoke, verify_result
from test_contracts import make_spec, metadata


class SmokeTests(unittest.TestCase):
    def test_known_reference(self):
        result = run_smoke(make_spec(), metadata())
        self.assertEqual(result.values, [43, 46, 51, 58, 67, 78, 91, 5])
        self.assertEqual(result.metrics, {"sample_count": 8, "integer_sum": 439,
                                         "reference_check": 1, "deterministic_check": 1})
        self.assertEqual(result.status, "PASS")
        verify_result(make_spec(), result, canonical_json(result.payload))

    def test_explicit_arithmetic(self):
        self.assertEqual(arithmetic_values(0, 4, 7), [1, 4, 2, 2])
        self.assertEqual(arithmetic_values(1, 4, 7), [2, 5, 3, 3])

    def test_runtime_and_commit_are_outside_deterministic_payload(self):
        spec = make_spec()
        first = run_smoke(replace(spec, commit_sha="a" * 40), metadata("a" * 40))
        changed = metadata("b" * 40)
        changed.update(python_version="3.99.0", package_version="99.0.0", run_id="second",
                       timestamp_utc="2027-02-03T04:05:06+00:00", working_tree_dirty=True)
        second = run_smoke(replace(spec, commit_sha="b" * 40), changed)
        self.assertEqual(canonical_json(first.payload), canonical_json(second.payload))
        self.assertNotEqual(canonical_json(first.to_dict()), canonical_json(second.to_dict()))
        self.assertNotIn("commit_sha", first.payload)
        self.assertNotIn("python_version", first.payload)

    def test_no_rng_dependency_or_global_state_change(self):
        original = random.getstate()
        try:
            random.seed(123)
            state = random.getstate()
            with patch("random.Random", side_effect=AssertionError("RNG forbidden")), \
                    patch("random.random", side_effect=AssertionError("RNG forbidden")):
                first = run_smoke(make_spec(), metadata())
            self.assertEqual(random.getstate(), state)
            random.seed(999)
            second = run_smoke(make_spec(), metadata())
            self.assertEqual(first.payload, second.payload)
        finally:
            random.setstate(original)

    def test_commit_config_seed_and_code_identity(self):
        spec = replace(make_spec(), commit_sha="a" * 40)
        result = run_smoke(spec, metadata(spec.commit_sha))
        self.assertEqual(result.execution["commit_sha"], spec.commit_sha)
        self.assertEqual(result.seed, spec.seed)
        self.assertEqual(result.config_sha256, spec.config_sha256)
        self.assertEqual(result.code_sha256, code_sha256())
        with self.assertRaises(ValueError):
            run_smoke(spec, metadata("b" * 40))

    def test_reference_mismatch_is_a_preserved_fail(self):
        spec = replace(make_spec(), benchmark={"expected_values": [44, 46, 51, 58, 67, 78, 91, 5]})
        result = run_smoke(spec, metadata())
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.failure_reason, "REFERENCE_MISMATCH")
        self.assertEqual(result.metrics["integer_sum"], 439)
        self.assertEqual(result.metrics["reference_check"], 0)
        self.assertIsNone(result.promotion_status)
        self.assertIsNone(result.rejection_reason)
        with self.assertRaises(ValueError):
            verify_result(spec, result, canonical_json(result.payload))


if __name__ == "__main__":
    unittest.main()
