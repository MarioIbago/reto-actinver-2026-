"""Minimal local entrypoint for smoke, verification and explicit ledger append."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import importlib.metadata
import logging
from pathlib import Path
import platform
import subprocess
import sys

from .contracts import (ExperimentResult, ExperimentSpec, canonical_json, load_json,
                        require, validate_commit)
from .ledger import append_bundle, append_record
from .smoke import run_smoke, verify_result


def _execution(spec: ExperimentSpec, commit: str | None, run_id: str | None) -> dict:
    dirty = None
    if commit is None:
        commit = spec.commit_sha
    if commit is None:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
            dirty = bool(subprocess.check_output(
                ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError):
            commit = None
    validate_commit(commit)
    require(spec.commit_sha is None or spec.commit_sha == commit, "Supplied commit differs from spec")
    return {"commit_sha": commit, "working_tree_dirty": dirty,
            "python_version": platform.python_version(),
            "package_version": importlib.metadata.version("reto-actinver-2026"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "run_id": run_id}


def _bundle(directory: Path) -> tuple[ExperimentSpec, ExperimentResult, bytes]:
    spec = ExperimentSpec.from_dict(load_json(directory / "resolved_spec.json"))
    result = ExperimentResult.from_dict(load_json(directory / "result.json"))
    return spec, result, (directory / "payload.json").read_bytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    smoke = commands.add_parser("smoke", help="Run HARNESS_SMOKE_001 and write a new bundle")
    smoke.add_argument("--spec", type=Path, required=True)
    smoke.add_argument("--output-dir", type=Path, required=True)
    smoke.add_argument("--commit-sha")
    smoke.add_argument("--run-id")
    verify = commands.add_parser("verify", help="Verify a bundle against its spec and installed code")
    verify.add_argument("--output-dir", type=Path, required=True)
    verify.add_argument("--spec", type=Path, required=True, help="Trusted, versioned input spec")
    verify.add_argument("--commit-sha", help="Expected commit, when independently known")
    record = commands.add_parser("record", help="Append a checked PASS/FAIL bundle to a ledger")
    record.add_argument("--output-dir", type=Path, required=True)
    record.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.command == "smoke":
            spec = ExperimentSpec.from_dict(load_json(args.spec))
            execution = _execution(spec, args.commit_sha, args.run_id)
            spec = replace(spec, commit_sha=execution["commit_sha"])
            result = run_smoke(spec, execution)
            args.output_dir.mkdir(parents=True, exist_ok=False)
            for name, value in (("resolved_spec.json", spec.to_dict()),
                                ("payload.json", result.payload), ("result.json", result.to_dict())):
                (args.output_dir / name).write_bytes(canonical_json(value))
            append_record(args.output_dir / "ledger.jsonl", spec, result)
            logging.info("%s %s config=%s", result.experiment_id, result.status, result.config_sha256)
            sys.stdout.write(canonical_json(result.payload).decode("utf-8"))
            return 0 if result.status == "PASS" else 1
        if args.command == "verify":
            spec, result, payload = _bundle(args.output_dir)
            source = ExperimentSpec.from_dict(load_json(args.spec))
            require(source.config_sha256 == spec.config_sha256, "Bundle differs from trusted spec")
            expected_commit = args.commit_sha if args.commit_sha is not None else source.commit_sha
            if expected_commit is not None:
                validate_commit(expected_commit)
                require(spec.commit_sha == expected_commit, "Unexpected commit identity")
            verify_result(spec, result, payload)
            print(f"PASS {result.experiment_id}: payload, config, code and identity verified")
            return 0
        append_bundle(args.output_dir, args.ledger)
        print(f"PASS ledger append: {args.ledger}")
        return 0
    except (OSError, ValueError, importlib.metadata.PackageNotFoundError) as error:
        logging.error("FAIL %s", error)
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
