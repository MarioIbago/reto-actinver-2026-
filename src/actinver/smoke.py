"""Explicit integer arithmetic only; no RNG or financial interpretation."""

import hashlib
from pathlib import Path
from typing import Any

from .contracts import ExperimentResult, ExperimentSpec, canonical_json, require


def arithmetic_values(seed: int, sample_count: int, modulus: int) -> list[int]:
    return [(seed + (index + 1) ** 2) % modulus for index in range(sample_count)]


def code_sha256() -> str:
    """Identify the five packaged source files, independent of installation path."""
    directory = Path(__file__).parent
    sources = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
               for name in ("__init__.py", "contracts.py", "smoke.py", "ledger.py", "cli.py")}
    return hashlib.sha256(canonical_json(sources)).hexdigest()


def run_smoke(spec: ExperimentSpec, execution: dict[str, Any]) -> ExperimentResult:
    spec.to_dict()  # Revalidate nested mutable containers before executing.
    require(execution.get("commit_sha") == spec.commit_sha, "Spec/execution commit mismatch")
    args = (spec.seed, spec.parameters["sample_count"], spec.parameters["modulus"])
    values = arithmetic_values(*args)
    repeated = arithmetic_values(*args)
    reference_ok = values == spec.benchmark["expected_values"]
    deterministic = values == repeated
    reason = None
    if not deterministic:
        reason = "NON_DETERMINISTIC_OUTPUT"
    elif not reference_ok:
        reason = "REFERENCE_MISMATCH"
    return ExperimentResult(
        schema_version=1, experiment_id=spec.experiment_id,
        dataset_version=spec.dataset_version, universe_version=spec.universe_version,
        seed=spec.seed, config_sha256=spec.config_sha256, code_sha256=code_sha256(),
        status="PASS" if reason is None else "FAIL", values=values,
        metrics={"sample_count": len(values), "integer_sum": sum(values),
                 "reference_check": int(reference_ok), "deterministic_check": int(deterministic)},
        failure_reason=reason, execution=execution,
    )


def verify_result(spec: ExperimentSpec, result: ExperimentResult, payload: bytes) -> None:
    """Recompute the complete deterministic payload; a valid FAIL remains a failure."""
    expected = run_smoke(spec, result.execution)
    require(result.payload == expected.payload, "Result does not match spec and installed code")
    require(payload == canonical_json(result.payload), "payload.json is not canonical or was altered")
    require(result.status == "PASS", result.failure_reason or "Experiment FAIL")
