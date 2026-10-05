"""CLI for verified M7 signal registry and deterministic ensemble evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .ensemble import EnsembleError, evaluate_ensemble
from .m1 import M1DataError, load_universe, verify_source_material
from .research_factory import ResearchFactoryError, list_promoted_experiments


ROOT = Path(__file__).resolve().parents[2]


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


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise EnsembleError(f"cannot read JSON from {path}: {exc}") from exc


def _write_json(value: Any, output: str) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if output == "-":
        sys.stdout.write(rendered)
        return
    try:
        Path(output).write_text(rendered, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise EnsembleError(f"cannot write JSON to {output}: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-ensemble", description="M7 promoted-signal ensemble and OOS diagnostics")
    commands = parser.add_subparsers(dest="command", required=True)
    promoted = commands.add_parser("promotions", help="list latest verified M5 PROMOTE decisions")
    promoted.add_argument("--ledger", type=Path, default=Path("research/factory_ledger.jsonl"))
    promoted.add_argument("--output", default="-")
    evaluate = commands.add_parser("evaluate", help="calibrate and evaluate promoted signals point in time")
    evaluate.add_argument("--registry", type=Path, default=Path("research/signals/registry.json"))
    evaluate.add_argument("--case", type=Path, required=True, help="point-in-time training/validation/test/live observations JSON")
    evaluate.add_argument("--ledger", type=Path, default=Path("research/factory_ledger.jsonl"))
    evaluate.add_argument("--universe", type=Path, default=Path("data/metadata/actinver_universe_2026_v1.json"))
    evaluate.add_argument("--output", default="-")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ledger = _path(args.ledger)
        promotions = list_promoted_experiments(ledger)
        if args.command == "promotions":
            _write_json(promotions, args.output)
            return 0
        registry = _read_json(_path(args.registry))
        case = _read_json(_path(args.case))
        universe = load_universe(_path(args.universe))
        verify_source_material(universe, ROOT)
        instrument_ids = {record["instrument_id"] for record in universe["instruments"]}
        result = evaluate_ensemble(
            registry,
            case,
            promotions,
            instrument_ids=instrument_ids,
            verified_universe_version=universe["snapshot_id"],
        )
        _write_json(result, args.output)
        return 0
    except (EnsembleError, M1DataError, ResearchFactoryError, OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
