"""CLI for the M4 reproducible, time-aware validation engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from .execution_cli import _find_project_root
from .m1 import M1DataError, load_rules, verify_rule_source_material, verify_source_material
from .validation import ValidationError, evaluate_validation_case


ROOT = _find_project_root(Path.cwd())
RULES_PATH = ROOT / "config/actinver_rules.yaml"
UNIVERSE_PATH = ROOT / "data/metadata/actinver_universe_2026_v1.json"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _git_commit_sha() -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-m4")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate", help="evaluate aligned execution-aware return trials")
    evaluate.add_argument("--input", type=Path, required=True, help="versioned M4 validation-case JSON")
    evaluate.add_argument("--output", type=Path, required=True, help="new immutable result JSON file")
    evaluate.add_argument("--code-commit-sha", help="full code SHA; defaults to checkout HEAD")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        input_path = args.input.resolve()
        input_bytes = input_path.read_bytes()
        case = json.loads(
            input_bytes.decode("utf-8-sig"),
            parse_float=Decimal,
            parse_constant=lambda value: (_ for _ in ()).throw(ValidationError(f"Invalid JSON number {value}")),
            object_pairs_hook=_unique_object,
        )
        ruleset = load_rules(RULES_PATH)
        universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
        verify_rule_source_material(ruleset, ROOT)
        verify_source_material(universe, ROOT)
        result = evaluate_validation_case(case, ruleset)
        code_sha = args.code_commit_sha or _git_commit_sha()
        if len(code_sha) not in {40, 64} or any(character not in "0123456789abcdefABCDEF" for character in code_sha):
            raise ValidationError("code_commit_sha must be a full 40- or 64-character Git SHA")
        input_sha = hashlib.sha256(input_bytes).hexdigest()
        identity = {
            "schema_version": 1,
            "experiment_id": case["experiment_id"],
            "input_sha256": input_sha,
            "code_commit_sha": code_sha.lower(),
            "ruleset_id": ruleset["ruleset_id"],
            "universe_snapshot_id": universe["snapshot_id"],
            "dataset_version": case["dataset_version"],
        }
        result["run_provenance"] = {
            **identity,
            "validation_run_id": "actinver-m4-v1-" + hashlib.sha256(_canonical_json(identity)).hexdigest(),
        }
        result_bytes = _canonical_json(result)
        output_path = args.output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output_path.open("xb") as stream:
                stream.write(result_bytes)
        except FileExistsError as exc:
            raise ValidationError(f"Refusing to overwrite existing result: {output_path}") from exc
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "promotion_status": result["status_decision"],
                    "validation_run_id": result["run_provenance"]["validation_run_id"],
                    "output_path": str(output_path),
                    "input_sha256": input_sha,
                },
                sort_keys=True,
            )
        )
    except (
        ValidationError,
        M1DataError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        KeyError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
