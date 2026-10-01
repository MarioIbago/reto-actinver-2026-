"""Single-writer JSONL ledger, preserving complete positive and negative records."""

import hashlib
from pathlib import Path

from .contracts import ExperimentResult, ExperimentSpec, canonical_json, load_json, require


def append_record(path: Path, spec: ExperimentSpec, result: ExperimentResult) -> None:
    require(spec.commit_sha == result.execution["commit_sha"], "Ledger commit mismatch")
    require(spec.config_sha256 == result.config_sha256 and spec.seed == result.seed and
            spec.experiment_id == result.experiment_id, "Ledger experiment identity mismatch")
    record = {"schema_version": 1, "spec": spec.to_dict(), "result": result.to_dict(),
              "payload_sha256": hashlib.sha256(canonical_json(result.payload)).hexdigest()}
    line = canonical_json(record)
    if path.exists() and path.stat().st_size:
        # Never concatenate a new record onto a truncated prior JSON line.
        with path.open("rb") as existing:
            existing.seek(-1, 2)
            require(existing.read(1) == b"\n", "Ledger has an incomplete final line")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(line)
        stream.flush()


def append_bundle(directory: Path, ledger: Path) -> None:
    """Copy a schema-valid bundle to the ledger, including genuine FAIL results."""
    spec = ExperimentSpec.from_dict(load_json(directory / "resolved_spec.json"))
    result = ExperimentResult.from_dict(load_json(directory / "result.json"))
    from .smoke import run_smoke

    expected = run_smoke(spec, result.execution)
    require(result.payload == expected.payload, "Cannot record an altered result")
    require((directory / "payload.json").read_bytes() == canonical_json(result.payload),
            "Cannot record an altered payload")
    append_record(ledger, spec, result)
