"""Command-line entry point for M3 execution replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .execution import ExecutionError, simulate_execution
from .m1 import (
    M1DataError,
    load_rules,
    load_universe,
    verify_rule_source_material,
    verify_source_material,
)


def _find_project_root(start: Path) -> Path:
    markers = (
        Path("config/actinver_rules.yaml"),
        Path("data/metadata/actinver_universe_2026_v1.json"),
        Path("research/source_material/actinver_universe_symbols_raw.md"),
    )
    resolved_start = start.resolve()
    for candidate in (resolved_start, *resolved_start.parents):
        if all((candidate / marker).is_file() for marker in markers):
            return candidate
    return Path(__file__).resolve().parents[2]


ROOT = _find_project_root(Path.cwd())
RULES_PATH = ROOT / "config/actinver_rules.yaml"
UNIVERSE_PATH = ROOT / "data/metadata/actinver_universe_2026_v1.json"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ExecutionError(f"Duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _git_commit_sha() -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-exec")
    commands = parser.add_subparsers(dest="command", required=True)
    simulate = commands.add_parser("simulate", help="replay orders against market trades")
    simulate.add_argument("--input", type=Path, required=True, help="versioned simulation-case JSON")
    simulate.add_argument("--output", type=Path, help="write a new immutable result JSON file")
    simulate.add_argument("--code-commit-sha", help="full code SHA; defaults to the checkout HEAD")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        input_path = args.input.resolve()
        input_bytes = input_path.read_bytes()
        case = json.loads(input_bytes.decode("utf-8-sig"), object_pairs_hook=_unique_object)
        ruleset = load_rules(RULES_PATH)
        universe = load_universe(UNIVERSE_PATH)
        verify_rule_source_material(ruleset, ROOT)
        verify_source_material(universe, ROOT)
        result = simulate_execution(case, ruleset, universe)
        code_commit_sha = args.code_commit_sha or _git_commit_sha()
        if len(code_commit_sha) not in {40, 64} or any(
            character not in "0123456789abcdefABCDEF" for character in code_commit_sha
        ):
            raise ExecutionError("code_commit_sha must be a full 40- or 64-character Git SHA")
        input_sha256 = hashlib.sha256(input_bytes).hexdigest()
        run_identity = {
            "schema_version": 1,
            "input_sha256": input_sha256,
            "code_commit_sha": code_commit_sha.lower(),
            "ruleset_id": ruleset["ruleset_id"],
            "universe_snapshot_id": universe["snapshot_id"],
            "market_data_dataset_id": case["market_data_dataset_id"],
        }
        result["run_provenance"] = {
            **run_identity,
            "execution_id": "actinver-exec-v1-" + hashlib.sha256(_canonical_json(run_identity)).hexdigest(),
        }
        result_bytes = _canonical_json(result)
        if args.output:
            output_path = args.output.resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with output_path.open("xb") as stream:
                    stream.write(result_bytes)
            except FileExistsError as exc:
                raise ExecutionError(f"Refusing to overwrite existing result: {output_path}") from exc
            summary = {
                "status": result["status"],
                "execution_id": result["run_provenance"]["execution_id"],
                "output_path": str(output_path),
                "input_sha256": input_sha256,
            }
            print(json.dumps(summary, sort_keys=True))
        else:
            sys.stdout.buffer.write(result_bytes)
    except (
        ExecutionError,
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
