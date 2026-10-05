"""CLI for auditing and querying the M1 rules/universe snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from .m1 import (
    bmv_trading_day_status,
    M1DataError,
    diff_rules,
    diff_universes,
    eligible_instruments,
    load_rules,
    load_universe,
    validate_order,
    validate_portfolio,
    verify_source_material,
    verify_rule_source_material,
)


ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "config/actinver_rules.yaml"
UNIVERSE_PATH = ROOT / "data/metadata/actinver_universe_2026_v1.json"


def _json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-m1")
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser("audit", help="validate rules, universe and source fingerprints")
    audit.add_argument("--rules", type=Path, default=RULES_PATH)
    audit.add_argument("--universe", type=Path, default=UNIVERSE_PATH)

    eligible = commands.add_parser("eligible", help="list official-annex instruments for a date")
    eligible.add_argument("--as-of", required=True)
    eligible.add_argument("--universe", type=Path, default=UNIVERSE_PATH)

    market_day = commands.add_parser(
        "market-day", help="check the sourced BMV trading-day calendar for a date"
    )
    market_day.add_argument("--as-of", required=True)
    market_day.add_argument("--rules", type=Path, default=RULES_PATH)

    order = commands.add_parser("validate-order", help="screen a proposed order against M1 constraints")
    order.add_argument("--input", type=Path, required=True, help="JSON with order and portfolio objects")
    order.add_argument("--as-of", required=True)
    order.add_argument("--rules", type=Path, default=RULES_PATH)
    order.add_argument("--universe", type=Path, default=UNIVERSE_PATH)

    portfolio = commands.add_parser("validate-portfolio", help="screen a portfolio against M1 constraints")
    portfolio.add_argument("--input", type=Path, required=True, help="portfolio JSON")
    portfolio.add_argument("--as-of", required=True)
    portfolio.add_argument("--rules", type=Path, default=RULES_PATH)
    portfolio.add_argument("--universe", type=Path, default=UNIVERSE_PATH)

    diff = commands.add_parser("diff", help="report rule or universe snapshot changes")
    diff.add_argument("--kind", choices=("rules", "universe"), required=True)
    diff.add_argument("--previous", type=Path, required=True)
    diff.add_argument("--current", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "audit":
            rules = load_rules(args.rules)
            universe = load_universe(args.universe)
            verify_source_material(universe, ROOT)
            verify_rule_source_material(rules, ROOT)
            eligible_now = eligible_instruments(universe, "2026-10-05")
            result = {
                "status": "PASS",
                "ruleset_id": rules["ruleset_id"],
                "universe_snapshot_id": universe["snapshot_id"],
                "source_fingerprints": "PASS",
                "rule_source_captures": "PASS",
                "counts": universe["observed_counts"],
                "eligible_on_2026_10_05": len(eligible_now),
                "ambiguity_count": len(rules["ambiguities"]),
            }
        elif args.command == "eligible":
            universe = load_universe(args.universe)
            records = eligible_instruments(universe, args.as_of)
            result = {
                "snapshot_id": universe["snapshot_id"],
                "as_of": args.as_of,
                "count": len(records),
                "operational_symbol_status": "UNVERIFIED_IN_SIMULATOR",
                "instruments": [
                    {
                        "instrument_id": record["instrument_id"],
                        "category": record["category"],
                        "guide_symbol": record["guide_symbol"],
                        "platform_symbol": record["platform_symbol"],
                        "issuer_or_name": record["issuer_or_name"],
                    }
                    for record in records
                ],
            }
        elif args.command == "market-day":
            rules = load_rules(args.rules)
            result = bmv_trading_day_status(args.as_of, rules)
        elif args.command == "validate-order":
            inputs = _read_json(args.input)
            rules = load_rules(args.rules)
            universe = load_universe(args.universe)
            result = validate_order(inputs["order"], inputs["portfolio"], rules, universe, args.as_of)
        elif args.command == "validate-portfolio":
            inputs = _read_json(args.input)
            rules = load_rules(args.rules)
            universe = load_universe(args.universe)
            result = validate_portfolio(inputs, rules, universe, args.as_of)
        elif args.command == "diff":
            if args.kind == "rules":
                previous = yaml.safe_load(args.previous.read_text(encoding="utf-8"))
                current = yaml.safe_load(args.current.read_text(encoding="utf-8"))
                result = diff_rules(previous, current)
            else:
                result = diff_universes(_read_json(args.previous), _read_json(args.current))
        else:  # pragma: no cover - argparse enforces known commands
            raise M1DataError(f"Unknown command: {args.command}")
    except (M1DataError, KeyError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _json(result)
    if result.get("constraint_status") == "NON_COMPLIANT":
        return 3
    if result.get("constraint_status") == "INDETERMINATE":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
