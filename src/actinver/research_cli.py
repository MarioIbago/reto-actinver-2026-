"""Command line interface for preregistered M5 research batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .execution_cli import _find_project_root
from .m1 import load_rules, verify_rule_source_material, verify_source_material
from .research_factory import (
    ResearchFactoryError,
    code_identity,
    load_plan,
    register_plan,
    run_registered_batch,
    summarize_ledger,
    verify_ledger,
)


ROOT = _find_project_root(Path.cwd())


def _ledger_path(value: Path) -> Path:
    return (value if value.is_absolute() else ROOT / value).resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-research")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="pre-register immutable experiment inputs")
    register.add_argument("--plan", type=Path, required=True)
    register.add_argument("--ledger", type=Path, default=Path("research/factory_ledger.jsonl"))
    run = commands.add_parser("run-batch", help="run a previously registered M4 evaluation batch")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--ledger", type=Path, default=Path("research/factory_ledger.jsonl"))
    verify = commands.add_parser("verify-ledger", help="verify append-only ledger hashes and identities")
    verify.add_argument("--ledger", type=Path, default=Path("research/factory_ledger.jsonl"))
    summary = commands.add_parser("summary", help="count registered, tested, rejected, and promoted work")
    summary.add_argument("--ledger", type=Path, default=Path("research/factory_ledger.jsonl"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        ledger_path = _ledger_path(args.ledger)
        if args.command == "verify-ledger":
            print(json.dumps(verify_ledger(ledger_path), sort_keys=True))
            return 0
        if args.command == "summary":
            print(json.dumps(summarize_ledger(ledger_path), sort_keys=True))
            return 0
        plan_path = args.plan.resolve(strict=True)
        plan = load_plan(plan_path)
        identity = code_identity(ROOT)
        if args.command == "register":
            output = register_plan(
                plan,
                plan_path=plan_path,
                ledger_path=ledger_path,
                identity=identity,
            )
            print(json.dumps(output, sort_keys=True))
            return 0
        ruleset = load_rules(ROOT / "config/actinver_rules.yaml")
        verify_rule_source_material(ruleset, ROOT)
        universe = json.loads((ROOT / "data/metadata/actinver_universe_2026_v1.json").read_text(encoding="utf-8"))
        verify_source_material(universe, ROOT)
        output = run_registered_batch(
            plan,
            plan_path=plan_path,
            ledger_path=ledger_path,
            identity=identity,
            ruleset=ruleset,
        )
        results = output["results"]
        decisions = {name: sum(item["scientific_decision"] == name for item in results) for name in (
            "REJECT", "NEEDS_MORE_EVIDENCE", "PROMOTE"
        )}
        print(
            json.dumps(
                {
                    "batch_id": output["batch_id"],
                    "result_count": len(results),
                    "decision_counts": decisions,
                    "run_errors": sum(item["run_status"] == "RUN_ERROR" for item in results),
                    "ledger_record_sha256": output["ledger_record_sha256"],
                },
                sort_keys=True,
            )
        )
    except (ResearchFactoryError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
