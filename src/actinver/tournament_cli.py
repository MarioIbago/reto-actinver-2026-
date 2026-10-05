"""CLI for deterministic M8 rank-aware tournament scenario comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .m1 import (
    M1DataError,
    load_rules,
    load_universe,
    verify_rule_source_material,
    verify_source_material,
)
from .tournament import TournamentError, evaluate_tournament


def _repository_root(cwd: Path, module_path: Path) -> Path:
    """Locate checked-out M1 and prompt assets from an installed CLI."""
    resolved_cwd = cwd.resolve()
    candidates = [resolved_cwd, *resolved_cwd.parents, *module_path.resolve().parents]
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "prompts" / "CURRENT_PHASE.md"
        ).is_file():
            return candidate
    return resolved_cwd


ROOT = _repository_root(Path.cwd(), Path(__file__))


def _path(value: Path) -> Path:
    return (value if value.is_absolute() else ROOT / value).resolve()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value}")


def _read_json(path: Path) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        return value, raw
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise TournamentError(f"cannot read JSON from {path}: {exc}") from exc


def _write_json(value: Any, output: str) -> None:
    try:
        rendered = json.dumps(
            value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise TournamentError(f"result cannot be encoded as finite JSON: {exc}") from exc
    if output == "-":
        sys.stdout.write(rendered)
        return
    try:
        Path(output).write_text(rendered, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise TournamentError(f"cannot write JSON to {output}: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="actinver-tournament",
        description="Compare feasible M8 portfolio scenarios; never emits orders.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser(
        "evaluate", help="compare rank-aware, expected-return and Sharpe baselines"
    )
    evaluate.add_argument("--case", type=Path, required=True, help="versioned M8 case JSON")
    evaluate.add_argument("--m7-result", type=Path, help="exact M7 result JSON bound by the case SHA-256")
    evaluate.add_argument("--rules", type=Path, default=Path("config/actinver_rules.yaml"))
    evaluate.add_argument(
        "--universe", type=Path, default=Path("data/metadata/actinver_universe_2026_v1.json")
    )
    evaluate.add_argument("--output", default="-", help="result JSON path, or - for stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        case, _case_bytes = _read_json(_path(args.case))
        if args.m7_result is None:
            m7_result, m7_sha = None, None
        else:
            m7_result, raw_m7 = _read_json(_path(args.m7_result))
            m7_sha = hashlib.sha256(raw_m7).hexdigest()
        rules = load_rules(_path(args.rules))
        universe = load_universe(_path(args.universe))
        verify_source_material(universe, ROOT)
        verify_rule_source_material(rules, ROOT)
        result = evaluate_tournament(
            case,
            m7_result,
            m7_result_sha256=m7_sha,
            ruleset=rules,
            universe=universe,
        )
        _write_json(result, args.output)
        return 0
    except (TournamentError, M1DataError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
