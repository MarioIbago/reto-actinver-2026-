"""Pre-registered M4 experiment batches and tamper-evident research memory."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from typing import Any, Mapping

from .validation import ValidationError, evaluate_validation_case


class ResearchFactoryError(ValueError):
    """Raised when a research plan or its append-only history is inconsistent."""


_PLAN_FIELDS = {"schema_version", "batch_id", "experiments"}
_PLAN_EXPERIMENT_FIELDS = {
    "hypothesis_path",
    "hypothesis_sha256",
    "validation_case_path",
    "validation_case_sha256",
    "experiment_spec",
}
_HYPOTHESIS_FIELDS = {
    "schema_version",
    "hypothesis_id",
    "statement",
    "rationale",
    "source_references",
    "falsification_plan",
}
_EXPERIMENT_SPEC_FIELDS = {
    "schema_version",
    "experiment_id",
    "hypothesis",
    "strategy_family",
    "dataset_version",
    "universe_version",
    "features",
    "target",
    "horizon",
    "parameters",
    "train_period",
    "validation_period",
    "test_period",
    "transaction_cost_model",
    "execution_model",
    "benchmark_trial_id",
    "promotion_criteria",
    "seed",
    "commit_sha",
    "periods_per_year",
    "attempted_trial_count",
    "validation_protocol",
    "evidence",
}
_EVIDENCE_FIELDS = {
    "data_status", "source_availability_verified", "instrument_mapping_verified",
    "m3_execution_evidence_verified", "costs_verified", "final_holdout_locked",
    "test_used_for_selection", "dataset_manifest_sha256", "m3_result_sha256",
}
_PROMOTION_FIELDS = {
    "minimum_test_sessions", "minimum_test_sharpe", "minimum_test_cumulative_return",
    "minimum_improvement_vs_benchmark", "minimum_dsr_probability", "maximum_pbo_probability",
    "maximum_test_drawdown",
}
_FALSIFICATION_CATEGORIES = {
    "leakage",
    "regime",
    "outliers",
    "parameter_sensitivity",
    "liquidity",
    "costs",
    "sample_size",
    "multiple_testing",
}
_DECISIONS = {"REJECT", "NEEDS_MORE_EVIDENCE", "PROMOTE"}
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_CODE_FILES = (
    "pyproject.toml",
    "src/actinver/baselines.py",
    "src/actinver/execution.py",
    "src/actinver/execution_cli.py",
    "src/actinver/research_factory.py",
    "src/actinver/research_cli.py",
    "src/actinver/validation.py",
    "src/actinver/validation_cli.py",
    "src/actinver/m1.py",
    "config/actinver_rules.yaml",
    "data/metadata/actinver_universe_2026_v1.json",
    "schemas/validation_case.schema.json",
    "schemas/validation_result.schema.json",
    "schemas/research_hypothesis.schema.json",
    "schemas/research_plan.schema.json",
    "schemas/research_experiment_spec.schema.json",
    "schemas/research_ledger_record.schema.json",
)


def _canonical(value: Any) -> bytes:
    try:
        return (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ResearchFactoryError(f"value is not canonical JSON: {exc}") from exc


def _object(value: Any, field: str, required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise ResearchFactoryError(f"{field} must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise ResearchFactoryError(f"{field} is missing fields: {', '.join(missing)}")
    if unknown:
        raise ResearchFactoryError(f"{field} has unknown fields: {', '.join(unknown)}")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchFactoryError(f"{field} must be non-empty text")
    return value.strip()


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ResearchFactoryError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _exact_decimal(value: Any, field: str, *, minimum: Decimal | None = Decimal(0)) -> Decimal:
    if not isinstance(value, str):
        raise ResearchFactoryError(f"{field} must be an exact decimal string")
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise ResearchFactoryError(f"{field} must be a valid decimal string") from exc
    if not parsed.is_finite() or (minimum is not None and parsed < minimum):
        raise ResearchFactoryError(f"{field} must be finite" + (f" and at least {minimum}" if minimum is not None else ""))
    return parsed


def _utc(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ResearchFactoryError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchFactoryError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ResearchFactoryError(f"{field} must be expressed in UTC")
    return parsed.astimezone(timezone.utc).isoformat()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchFactoryError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _load_json_bytes(raw: bytes, field: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ResearchFactoryError(f"{field} contains invalid JSON constant {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResearchFactoryError(f"{field} is not valid UTF-8 JSON: {exc}") from exc


def _validate_hypothesis(value: Any, field: str) -> dict[str, Any]:
    item = _object(value, field, _HYPOTHESIS_FIELDS)
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise ResearchFactoryError(f"{field}.schema_version must equal 1")
    _text(item["hypothesis_id"], f"{field}.hypothesis_id")
    _text(item["statement"], f"{field}.statement")
    _text(item["rationale"], f"{field}.rationale")
    refs = item["source_references"]
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ResearchFactoryError(f"{field}.source_references must be an array of non-empty strings")
    plan = item["falsification_plan"]
    if not isinstance(plan, list):
        raise ResearchFactoryError(f"{field}.falsification_plan must be an array")
    categories = set()
    for index, raw_check in enumerate(plan):
        check = _object(raw_check, f"{field}.falsification_plan[{index}]", {"category", "approach", "required"})
        category = _text(check["category"], f"{field}.falsification_plan[{index}].category")
        if category not in _FALSIFICATION_CATEGORIES:
            raise ResearchFactoryError(f"unsupported falsification category {category!r}")
        if category in categories:
            raise ResearchFactoryError(f"duplicate falsification category {category!r}")
        categories.add(category)
        _text(check["approach"], f"{field}.falsification_plan[{index}].approach")
        if type(check["required"]) is not bool:
            raise ResearchFactoryError(f"{field}.falsification_plan[{index}].required must be boolean")
        if check["required"] is not True:
            raise ResearchFactoryError(f"{field}.falsification_plan category {category!r} must be required")
    if categories != _FALSIFICATION_CATEGORIES:
        missing = sorted(_FALSIFICATION_CATEGORIES - categories)
        raise ResearchFactoryError(f"{field}.falsification_plan must cover all categories: {', '.join(missing)}")
    return item


def _validate_experiment_spec(value: Any, field: str = "experiment_spec") -> dict[str, Any]:
    """Validate the M5 research contract independently of M4's return-series case."""
    spec = _object(value, field, _EXPERIMENT_SPEC_FIELDS)
    if type(spec["schema_version"]) is not int or spec["schema_version"] != 1:
        raise ResearchFactoryError(f"{field}.schema_version must equal 1")
    for name in (
        "experiment_id", "hypothesis", "strategy_family", "dataset_version", "universe_version",
        "target", "horizon", "benchmark_trial_id", "execution_model",
    ):
        _text(spec[name], f"{field}.{name}")
    if spec["commit_sha"] is not None and (
        not isinstance(spec["commit_sha"], str) or re.fullmatch(r"[0-9a-f]{40}", spec["commit_sha"]) is None
    ):
        raise ResearchFactoryError(f"{field}.commit_sha must be null or a full lowercase Git SHA")
    if type(spec["seed"]) is not int or spec["seed"] < 0:
        raise ResearchFactoryError(f"{field}.seed must be a non-negative integer")
    if type(spec["periods_per_year"]) is not int or spec["periods_per_year"] < 1:
        raise ResearchFactoryError(f"{field}.periods_per_year must be a positive integer")
    if type(spec["attempted_trial_count"]) is not int or spec["attempted_trial_count"] < 1:
        raise ResearchFactoryError(f"{field}.attempted_trial_count must be a positive integer")
    features = spec["features"]
    if not isinstance(features, list) or any(not isinstance(name, str) or not name.strip() for name in features):
        raise ResearchFactoryError(f"{field}.features must be an array of non-empty strings")
    parsed_periods = {}
    for name in ("train_period", "validation_period", "test_period"):
        period = _object(spec[name], f"{field}.{name}", {"start", "end"})
        try:
            start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
        except (TypeError, ValueError) as exc:
            raise ResearchFactoryError(f"{field}.{name} must have ISO-8601 dates") from exc
        if period["start"] != start.isoformat() or period["end"] != end.isoformat():
            raise ResearchFactoryError(f"{field}.{name} dates must use canonical YYYY-MM-DD format")
        if start > end:
            raise ResearchFactoryError(f"{field}.{name}.start must not follow its end")
        parsed_periods[name] = (start, end)
    if not (
        parsed_periods["train_period"][1] < parsed_periods["validation_period"][0]
        and parsed_periods["validation_period"][1] < parsed_periods["test_period"][0]
    ):
        raise ResearchFactoryError(f"{field} train, validation, and test periods must be chronological and non-overlapping")
    variants = spec["parameters"]
    if not isinstance(variants, list) or len(variants) < 2:
        raise ResearchFactoryError(f"{field}.parameters must list at least two reference variants")
    trial_ids = set()
    for index, variant in enumerate(variants):
        trial = _object(variant, f"{field}.parameters[{index}]", {"trial_id", "parameters", "parameter_sha256"})
        trial_id = _text(trial["trial_id"], f"{field}.parameters[{index}].trial_id")
        if trial_id in trial_ids:
            raise ResearchFactoryError(f"{field}.parameters contains duplicate trial_id {trial_id!r}")
        trial_ids.add(trial_id)
        params = trial["parameters"]
        if not isinstance(params, dict) or any(
            type(key) is not str or not key.strip() or item is not None and type(item) not in (str, int, bool)
            for key, item in params.items()
        ):
            raise ResearchFactoryError(f"{field}.parameters[{index}].parameters must contain scalar values")
        if _sha256(trial["parameter_sha256"], f"{field}.parameters[{index}].parameter_sha256") != hashlib.sha256(_canonical(params)).hexdigest():
            raise ResearchFactoryError(f"{field}.parameters[{index}] parameter fingerprint does not match")
    if spec["attempted_trial_count"] < len(variants):
        raise ResearchFactoryError(f"{field}.attempted_trial_count cannot be smaller than its parameter variants")
    if spec["benchmark_trial_id"] not in trial_ids:
        raise ResearchFactoryError(f"{field}.benchmark_trial_id must name one of its parameter variants")
    cost = _object(
        spec["transaction_cost_model"],
        f"{field}.transaction_cost_model",
        {"ruleset_id", "commission_rate", "iva_rate_on_commission", "slippage_bps_per_side", "turnover_definition"},
    )
    _text(cost["ruleset_id"], f"{field}.transaction_cost_model.ruleset_id")
    _exact_decimal(cost["commission_rate"], f"{field}.transaction_cost_model.commission_rate")
    _exact_decimal(cost["iva_rate_on_commission"], f"{field}.transaction_cost_model.iva_rate_on_commission")
    _text(cost["turnover_definition"], f"{field}.transaction_cost_model.turnover_definition")
    slippage = cost["slippage_bps_per_side"]
    if not isinstance(slippage, list) or not slippage:
        raise ResearchFactoryError(f"{field}.transaction_cost_model.slippage_bps_per_side must be non-empty")
    parsed_slippage = [_exact_decimal(item, f"{field}.transaction_cost_model.slippage_bps_per_side[]") for item in slippage]
    if len(set(parsed_slippage)) != len(parsed_slippage):
        raise ResearchFactoryError(f"{field}.transaction_cost_model slippage values must be unique")
    _object(spec["validation_protocol"], f"{field}.validation_protocol", {"bootstrap", "walk_forward", "pbo"})
    evidence = _object(spec["evidence"], f"{field}.evidence", _EVIDENCE_FIELDS)
    if evidence["data_status"] not in {"synthetic_fixture", "authorized_point_in_time", "unverified"}:
        raise ResearchFactoryError(f"{field}.evidence.data_status is unsupported")
    for flag in _EVIDENCE_FIELDS - {"data_status", "dataset_manifest_sha256", "m3_result_sha256"}:
        if type(evidence[flag]) is not bool:
            raise ResearchFactoryError(f"{field}.evidence.{flag} must be boolean")
    for digest in ("dataset_manifest_sha256", "m3_result_sha256"):
        _sha256(evidence[digest], f"{field}.evidence.{digest}") if evidence[digest] is not None else None
    criteria = _object(spec["promotion_criteria"], f"{field}.promotion_criteria", _PROMOTION_FIELDS)
    if type(criteria["minimum_test_sessions"]) is not int or criteria["minimum_test_sessions"] < 1:
        raise ResearchFactoryError(f"{field}.promotion_criteria.minimum_test_sessions must be positive")
    for key in _PROMOTION_FIELDS - {"minimum_test_sessions"}:
        value = _exact_decimal(criteria[key], f"{field}.promotion_criteria.{key}", minimum=None)
        if key in {"minimum_dsr_probability", "maximum_pbo_probability", "maximum_test_drawdown"} and not Decimal(0) <= value <= Decimal(1):
            raise ResearchFactoryError(f"{field}.promotion_criteria.{key} must be in [0, 1]")
    return spec


def validate_plan(value: Any) -> dict[str, Any]:
    """Validate the closed M5 plan contract before registering or running it."""
    plan = _object(value, "plan", _PLAN_FIELDS)
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        raise ResearchFactoryError("plan.schema_version must equal 1")
    batch_id = _text(plan["batch_id"], "plan.batch_id")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,63}", batch_id) is None:
        raise ResearchFactoryError("plan.batch_id must be 3-64 letters, digits, dots, underscores, or hyphens")
    experiments = plan["experiments"]
    if not isinstance(experiments, list) or not experiments:
        raise ResearchFactoryError("plan.experiments must be a non-empty array")
    for index, raw_experiment in enumerate(experiments):
        experiment = _object(raw_experiment, f"plan.experiments[{index}]", _PLAN_EXPERIMENT_FIELDS)
        for field in ("hypothesis_path", "validation_case_path"):
            _text(experiment[field], f"plan.experiments[{index}].{field}")
        _sha256(experiment["hypothesis_sha256"], f"plan.experiments[{index}].hypothesis_sha256")
        _sha256(experiment["validation_case_sha256"], f"plan.experiments[{index}].validation_case_sha256")
        _validate_experiment_spec(experiment["experiment_spec"], f"plan.experiments[{index}].experiment_spec")
    return plan


def load_plan(path: Path) -> dict[str, Any]:
    try:
        value = _load_json_bytes(path.resolve(strict=True).read_bytes(), "research plan")
    except OSError as exc:
        raise ResearchFactoryError(f"cannot read research plan: {exc}") from exc
    return validate_plan(value)


def _resolve_ref(plan_path: Path, value: str) -> Path:
    candidate = Path(value)
    return (candidate if candidate.is_absolute() else plan_path.parent / candidate).resolve(strict=True)


def _read_registered_inputs(plan: Mapping[str, Any], plan_path: Path) -> list[dict[str, Any]]:
    prepared = []
    experiment_ids = set()
    for index, item in enumerate(plan["experiments"]):
        try:
            hypothesis_path = _resolve_ref(plan_path, item["hypothesis_path"])
            hypothesis_bytes = hypothesis_path.read_bytes()
            hypothesis_digest = hashlib.sha256(hypothesis_bytes).hexdigest()
            if hypothesis_digest != item["hypothesis_sha256"]:
                raise ResearchFactoryError(f"experiments[{index}] hypothesis file fingerprint changed")
            hypothesis = _validate_hypothesis(_load_json_bytes(hypothesis_bytes, "hypothesis"), "hypothesis")
            experiment_spec = _validate_experiment_spec(item["experiment_spec"])

            case_path = _resolve_ref(plan_path, item["validation_case_path"])
            case_bytes = case_path.read_bytes()
            case_digest = hashlib.sha256(case_bytes).hexdigest()
            if case_digest != item["validation_case_sha256"]:
                raise ResearchFactoryError(f"experiments[{index}] validation case fingerprint changed")
            case = _load_json_bytes(case_bytes, "validation case")
            if not isinstance(case, dict):
                raise ResearchFactoryError(f"experiments[{index}] validation case must be an object")
            _validate_case_parameter_fingerprints(case)
            experiment_id = _text(case.get("experiment_id"), f"experiments[{index}].experiment_id")
            if experiment_id in experiment_ids:
                raise ResearchFactoryError(f"duplicate experiment_id {experiment_id!r} in batch")
            experiment_ids.add(experiment_id)
            if case.get("hypothesis") != hypothesis["statement"]:
                raise ResearchFactoryError(f"experiments[{index}] hypothesis statement does not match its M4 case")
            _validate_spec_matches_case(experiment_spec, case, hypothesis)
            prepared.append(
                {
                    "experiment_id": experiment_id,
                    "hypothesis_id": hypothesis["hypothesis_id"],
                    "hypothesis_path": item["hypothesis_path"],
                    "hypothesis_sha256": hypothesis_digest,
                    "validation_case_path": item["validation_case_path"],
                    "validation_case_sha256": case_digest,
                    "hypothesis": hypothesis,
                    "experiment_spec": experiment_spec,
                    "case": case,
                }
            )
        except OSError as exc:
            raise ResearchFactoryError(f"experiments[{index}] input cannot be read: {exc}") from exc
    return prepared


def _validate_case_parameter_fingerprints(case: Mapping[str, Any]) -> None:
    """Reject malformed or stale M4 parameter hashes before comparing snapshots."""
    trials = case.get("trials")
    if not isinstance(trials, list):
        raise ResearchFactoryError("validation case.trials must be an array")
    for index, raw_trial in enumerate(trials):
        trial = _object(
            raw_trial,
            f"validation case.trials[{index}]",
            {"trial_id", "parameters", "parameter_sha256", "returns"},
        )
        parameters = trial["parameters"]
        if not isinstance(parameters, dict):
            raise ResearchFactoryError(f"validation case.trials[{index}].parameters must be an object")
        fingerprint = _sha256(
            trial["parameter_sha256"],
            f"validation case.trials[{index}].parameter_sha256",
        )
        if fingerprint != hashlib.sha256(_canonical(parameters)).hexdigest():
            raise ResearchFactoryError(
                f"validation case.trials[{index}] parameter fingerprint does not match its parameters"
            )


def _validate_spec_matches_case(
    spec: Mapping[str, Any],
    case: Mapping[str, Any],
    hypothesis: Mapping[str, Any],
) -> None:
    if spec["experiment_id"] != case.get("experiment_id") or spec["hypothesis"] != hypothesis["statement"]:
        raise ResearchFactoryError("ExperimentSpec identity/hypothesis does not match its M4 validation case")
    for field in (
        "dataset_version", "universe_version", "train_period", "validation_period", "test_period",
        "benchmark_trial_id", "promotion_criteria", "seed", "periods_per_year", "attempted_trial_count",
        "commit_sha", "evidence",
    ):
        if spec[field] != case.get(field):
            raise ResearchFactoryError(f"ExperimentSpec.{field} does not match its M4 validation case")
    trial_parameters = [
        {"trial_id": trial.get("trial_id"), "parameters": trial.get("parameters"), "parameter_sha256": trial.get("parameter_sha256")}
        for trial in case.get("trials", [])
    ]
    if spec["parameters"] != trial_parameters:
        raise ResearchFactoryError("ExperimentSpec parameter variants do not match the M4 validation case")
    protocol = spec["validation_protocol"]
    for field in ("bootstrap", "walk_forward", "pbo"):
        if protocol[field] != case.get(field):
            raise ResearchFactoryError(f"ExperimentSpec.validation_protocol.{field} does not match the M4 validation case")
    if spec["transaction_cost_model"]["slippage_bps_per_side"] != case.get("cost_sensitivity_bps"):
        raise ResearchFactoryError("ExperimentSpec slippage cases do not match the M4 validation case")


def code_identity(root: Path) -> dict[str, Any]:
    """Identify relevant code/config and whether any of those tracked inputs are dirty."""
    root = root.resolve()
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty_result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all", "--", *_CODE_FILES],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ResearchFactoryError(f"cannot identify Git checkout: {exc}") from exc
    if _COMMIT.fullmatch(commit) is None:
        raise ResearchFactoryError("Git did not return a full lowercase commit SHA")
    components = {}
    for relative in _CODE_FILES:
        path = root / relative
        try:
            source = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            components[relative] = hashlib.sha256(source).hexdigest()
        except OSError as exc:
            raise ResearchFactoryError(f"required provenance file {relative} is unavailable: {exc}") from exc
    try:
        package_version = importlib.metadata.version("reto-actinver-2026")
        yaml_version = importlib.metadata.version("PyYAML")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ResearchFactoryError("install the package before using the research factory") from exc
    return {
        "commit_sha": commit,
        "code_tree_sha256": hashlib.sha256(_canonical(components)).hexdigest(),
        "working_tree_dirty": bool(dirty_result.stdout.strip()),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "package_version": package_version,
        "dependency_versions": {"PyYAML": yaml_version},
    }


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    previous = None
    registered: dict[str, dict[str, Any]] = {}
    completed = set()
    try:
        raw_lines = path.read_bytes().splitlines(keepends=True)
    except OSError as exc:
        raise ResearchFactoryError(f"cannot read ledger: {exc}") from exc
    for index, raw_line in enumerate(raw_lines, start=1):
        if not raw_line.endswith(b"\n"):
            raise ResearchFactoryError(f"ledger line {index} is incomplete")
        record = _load_json_bytes(raw_line, f"ledger line {index}")
        if not isinstance(record, dict) or "record_sha256" not in record:
            raise ResearchFactoryError(f"ledger line {index} is not a versioned record")
        record_digest = _sha256(record["record_sha256"], f"ledger line {index}.record_sha256")
        body = {key: value for key, value in record.items() if key != "record_sha256"}
        expected_digest = hashlib.sha256(_canonical(body)).hexdigest()
        if record_digest != expected_digest:
            raise ResearchFactoryError(f"ledger line {index} record fingerprint mismatch")
        if raw_line != _canonical(record):
            raise ResearchFactoryError(f"ledger line {index} is not canonical JSON")
        if type(body.get("schema_version")) is not int or body.get("schema_version") != 1 or type(body.get("sequence")) is not int or body.get("sequence") != index:
            raise ResearchFactoryError(f"ledger line {index} has an unsupported version or sequence")
        if body.get("previous_record_sha256") != previous:
            raise ResearchFactoryError(f"ledger line {index} hash chain is broken")
        batch_id = body.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            raise ResearchFactoryError(f"ledger line {index} has no batch_id")
        event_type = body.get("event_type")
        if event_type == "plan_registered":
            required_record_keys = {
                "schema_version", "sequence", "previous_record_sha256", "event_type", "batch_id",
                "created_at_utc", "plan_sha256", "code_identity", "plan", "registered_experiments", "record_sha256",
            }
            if record.keys() != required_record_keys:
                raise ResearchFactoryError(f"ledger line {index} registration record has unknown or missing fields")
            if batch_id in registered:
                raise ResearchFactoryError(f"ledger contains duplicate registration for batch {batch_id}")
            plan = validate_plan(body.get("plan"))
            plan_digest = hashlib.sha256(_canonical(plan)).hexdigest()
            if plan["batch_id"] != batch_id or body.get("plan_sha256") != plan_digest:
                raise ResearchFactoryError(f"ledger line {index} plan identity/fingerprint mismatch")
            _validate_code_identity(body.get("code_identity"), f"ledger line {index}.code_identity")
            created_at = _utc(body.get("created_at_utc"), f"ledger line {index}.created_at_utc")
            registered_experiments = body.get("registered_experiments")
            if not isinstance(registered_experiments, list) or len(registered_experiments) != len(plan["experiments"]):
                raise ResearchFactoryError(f"ledger line {index} must identify every registered experiment")
            normalized_experiments = []
            seen_ids = set()
            for experiment_index, item in enumerate(registered_experiments):
                registered_item = _object(
                    item,
                    "registered experiment",
                    {"hypothesis_id", "experiment_id", "hypothesis", "experiment_spec"},
                )
                _text(registered_item["hypothesis_id"], "registered experiment.hypothesis_id")
                experiment_id = _text(registered_item["experiment_id"], "registered experiment.experiment_id")
                hypothesis = _validate_hypothesis(registered_item["hypothesis"], "registered experiment.hypothesis")
                if hypothesis["hypothesis_id"] != registered_item["hypothesis_id"]:
                    raise ResearchFactoryError(f"ledger line {index} hypothesis ID does not match its snapshot")
                specification = _validate_experiment_spec(registered_item["experiment_spec"], "registered experiment.experiment_spec")
                if specification["experiment_id"] != experiment_id or specification["hypothesis"] != hypothesis["statement"]:
                    raise ResearchFactoryError(f"ledger line {index} specification does not match its hypothesis")
                planned_specification = plan["experiments"][experiment_index]["experiment_spec"]
                if specification != planned_specification:
                    raise ResearchFactoryError(f"ledger line {index} registered ExperimentSpec does not match its plan")
                if len(specification["parameters"]) < 2:
                    raise ResearchFactoryError(f"ledger line {index} ExperimentSpec does not preserve parameter variants")
                if experiment_id in seen_ids:
                    raise ResearchFactoryError(f"ledger line {index} has duplicate registered experiment IDs")
                seen_ids.add(experiment_id)
                normalized_experiments.append(registered_item)
            registered[batch_id] = {
                "plan": plan,
                "plan_sha256": plan_digest,
                "code_identity": body["code_identity"],
                "registered_experiments": normalized_experiments,
                "created_at_utc": created_at,
            }
        elif event_type == "batch_completed":
            required_record_keys = {
                "schema_version", "sequence", "previous_record_sha256", "event_type", "batch_id",
                "completed_at_utc", "plan_sha256", "code_identity", "results", "record_sha256",
            }
            if record.keys() != required_record_keys:
                raise ResearchFactoryError(f"ledger line {index} completion record has unknown or missing fields")
            registration = registered.get(batch_id)
            if registration is None:
                raise ResearchFactoryError(f"ledger line {index} completes an unregistered batch")
            if batch_id in completed:
                raise ResearchFactoryError(f"ledger contains duplicate completion for batch {batch_id}")
            if body.get("plan_sha256") != registration["plan_sha256"]:
                raise ResearchFactoryError(f"ledger line {index} plan fingerprint does not match registration")
            _validate_code_identity(body.get("code_identity"), f"ledger line {index}.code_identity")
            if body["code_identity"] != registration["code_identity"]:
                raise ResearchFactoryError(f"ledger line {index} code identity differs from registration")
            completed_at = _utc(body.get("completed_at_utc"), f"ledger line {index}.completed_at_utc")
            if datetime.fromisoformat(completed_at) < datetime.fromisoformat(registration["created_at_utc"]):
                raise ResearchFactoryError(f"ledger line {index} completes before preregistration")
            results = body.get("results")
            expected_experiments = {item["experiment_id"] for item in registration["registered_experiments"]}
            if not isinstance(results, list) or len(results) != len(expected_experiments):
                raise ResearchFactoryError(f"ledger line {index} must preserve one result per planned experiment")
            seen = set()
            for result in results:
                _validate_experiment_result(result, expected_experiments)
                if result["experiment_id"] in seen:
                    raise ResearchFactoryError(f"ledger line {index} has duplicate experiment results")
                seen.add(result["experiment_id"])
                registered_item = next(
                    item for item in registration["registered_experiments"]
                    if item["experiment_id"] == result["experiment_id"]
                )
                plan_item = next(
                    item for item in registration["plan"]["experiments"]
                    if item["experiment_spec"]["experiment_id"] == result["experiment_id"]
                )
                if result["hypothesis_id"] != registered_item["hypothesis_id"]:
                    raise ResearchFactoryError(f"ledger line {index} result hypothesis does not match preregistration")
                for field in (
                    "hypothesis_path", "hypothesis_sha256", "validation_case_path", "validation_case_sha256",
                ):
                    if result[field] != plan_item[field]:
                        raise ResearchFactoryError(f"ledger line {index} result {field} does not match preregistration")
            if seen != expected_experiments:
                raise ResearchFactoryError(f"ledger line {index} result identities do not match its plan")
            completed.add(batch_id)
        else:
            raise ResearchFactoryError(f"ledger line {index} has unsupported event type {event_type!r}")
        records.append(record)
        previous = record_digest
    return records


def _validate_code_identity(value: Any, field: str) -> dict[str, Any]:
    item = _object(value, field, {
        "commit_sha", "code_tree_sha256", "working_tree_dirty", "python_version", "platform",
        "package_version", "dependency_versions",
    })
    if not isinstance(item["commit_sha"], str) or _COMMIT.fullmatch(item["commit_sha"]) is None:
        raise ResearchFactoryError(f"{field}.commit_sha must be a full lowercase Git SHA")
    _sha256(item["code_tree_sha256"], f"{field}.code_tree_sha256")
    if type(item["working_tree_dirty"]) is not bool:
        raise ResearchFactoryError(f"{field}.working_tree_dirty must be boolean")
    _text(item["python_version"], f"{field}.python_version")
    _text(item["platform"], f"{field}.platform")
    _text(item["package_version"], f"{field}.package_version")
    dependencies = _object(item["dependency_versions"], f"{field}.dependency_versions", {"PyYAML"})
    _text(dependencies["PyYAML"], f"{field}.dependency_versions.PyYAML")
    return item


def _validate_experiment_result(value: Any, expected_ids: set[str]) -> dict[str, Any]:
    required = {
        "hypothesis_id", "experiment_id", "hypothesis_path", "hypothesis_sha256",
        "validation_case_path", "validation_case_sha256", "run_status", "m4_decision",
        "scientific_decision", "m5_gate_downgraded", "decision_reasons", "falsification_checks",
        "validation_result", "error",
    }
    item = _object(value, "experiment result", required)
    _text(item["hypothesis_id"], "experiment result.hypothesis_id")
    if item["experiment_id"] not in expected_ids:
        raise ResearchFactoryError("experiment result has an unexpected experiment_id")
    if item["run_status"] not in {"COMPLETED", "RUN_ERROR"}:
        raise ResearchFactoryError("experiment result.run_status is unsupported")
    if item["scientific_decision"] not in _DECISIONS:
        raise ResearchFactoryError("experiment result.scientific_decision is unsupported")
    if type(item["m5_gate_downgraded"]) is not bool:
        raise ResearchFactoryError("experiment result.m5_gate_downgraded must be boolean")
    for field in ("hypothesis_path", "validation_case_path"):
        _text(item[field], f"experiment result.{field}")
    for field in ("hypothesis_sha256", "validation_case_sha256"):
        _sha256(item[field], f"experiment result.{field}")
    if not isinstance(item["decision_reasons"], list) or any(not isinstance(x, str) for x in item["decision_reasons"]):
        raise ResearchFactoryError("experiment result.decision_reasons must be an array of strings")
    if not isinstance(item["falsification_checks"], list):
        raise ResearchFactoryError("experiment result.falsification_checks must be an array")
    for check in item["falsification_checks"]:
        normalized_check = _object(check, "falsification check", {"category", "required", "status", "approach", "reason", "details"})
        if normalized_check["category"] not in _FALSIFICATION_CATEGORIES:
            raise ResearchFactoryError("falsification check has unsupported category")
        if type(normalized_check["required"]) is not bool:
            raise ResearchFactoryError("falsification check.required must be boolean")
        if normalized_check["required"] is not True:
            raise ResearchFactoryError("all recorded M5 falsification checks must be required")
        if normalized_check["status"] not in {"CHECKED", "FAILED", "NOT_AVAILABLE", "NOT_IMPLEMENTED", "INSUFFICIENT"}:
            raise ResearchFactoryError("falsification check has unsupported status")
        _text(normalized_check["approach"], "falsification check.approach")
        _text(normalized_check["reason"], "falsification check.reason")
        if not isinstance(normalized_check["details"], dict):
            raise ResearchFactoryError("falsification check.details must be an object")
    if item["run_status"] == "COMPLETED":
        if not isinstance(item["validation_result"], dict) or item["error"] is not None:
            raise ResearchFactoryError("completed experiment result must include a validation result")
        m4_decision = item["validation_result"].get("status_decision")
        if item["m4_decision"] not in _DECISIONS:
            raise ResearchFactoryError("completed experiment result.m4_decision is unsupported")
        if item["m4_decision"] != m4_decision or (
            m4_decision != item["scientific_decision"]
            and not (
                m4_decision == "PROMOTE"
                and item["scientific_decision"] == "NEEDS_MORE_EVIDENCE"
                and item["m5_gate_downgraded"]
            )
        ):
            raise ResearchFactoryError("completed experiment scientific decision does not match validation result")
    elif (
        item["m4_decision"] is not None
        or item["m5_gate_downgraded"]
        or item["validation_result"] is not None
        or not isinstance(item["error"], str)
        or not item["error"]
    ):
        raise ResearchFactoryError("run-error result must preserve its error and omit validation metrics")
    return item


def _event_body(
    *,
    records: list[dict[str, Any]],
    event_type: str,
    batch_id: str,
    **fields: Any,
) -> dict[str, Any]:
    previous = records[-1]["record_sha256"] if records else None
    return {
        "schema_version": 1,
        "sequence": len(records) + 1,
        "previous_record_sha256": previous,
        "event_type": event_type,
        "batch_id": batch_id,
        **fields,
    }


def _append_event(path: Path, body: dict[str, Any]) -> dict[str, Any]:
    records = _read_ledger(path)
    if body["sequence"] != len(records) + 1 or body["previous_record_sha256"] != (
        records[-1]["record_sha256"] if records else None
    ):
        raise ResearchFactoryError("ledger changed while this single-writer operation was running")
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    record = {**body, "record_sha256": digest}
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("ab") as stream:
            stream.write(_canonical(record))
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ResearchFactoryError(f"cannot append research ledger: {exc}") from exc
    _read_ledger(path)
    return record


def register_plan(
    plan: Any,
    *,
    plan_path: Path,
    ledger_path: Path,
    identity: Mapping[str, Any],
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Append an immutable preregistration record, idempotently for identical inputs."""
    normalized = validate_plan(plan)
    identity = _validate_code_identity(dict(identity), "code_identity")
    prepared = _read_registered_inputs(normalized, plan_path.resolve())
    digest = hashlib.sha256(_canonical(normalized)).hexdigest()
    records = _read_ledger(ledger_path)
    prior = next(
        (record for record in records if record["event_type"] == "plan_registered" and record["batch_id"] == normalized["batch_id"]),
        None,
    )
    if prior is not None:
        if prior["plan_sha256"] != digest or prior["code_identity"] != identity:
            raise ResearchFactoryError("batch_id is already registered with a different plan or code identity")
        return {"status": "ALREADY_REGISTERED", "batch_id": normalized["batch_id"], "plan_sha256": digest}
    created = _utc(now_utc or datetime.now(timezone.utc).isoformat(), "created_at_utc")
    registered_experiments = [
        {
            "hypothesis_id": item["hypothesis_id"],
            "experiment_id": item["experiment_id"],
            "hypothesis": item["hypothesis"],
            "experiment_spec": item["experiment_spec"],
        }
        for item in prepared
    ]
    body = _event_body(
        records=records,
        event_type="plan_registered",
        batch_id=normalized["batch_id"],
        created_at_utc=created,
        plan_sha256=digest,
        code_identity=dict(identity),
        plan=normalized,
        registered_experiments=registered_experiments,
    )
    _append_event(ledger_path, body)
    return {"status": "REGISTERED", "batch_id": normalized["batch_id"], "plan_sha256": digest}


def _validation_outlier_sensitivity(
    case: Mapping[str, Any],
    ruleset: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    validation_start = date.fromisoformat(case["validation_period"]["start"])
    validation_end = date.fromisoformat(case["validation_period"]["end"])
    fees = Decimal(str(ruleset["rules"]["costs"]["commission_rate"])) * (
        Decimal(1) + Decimal(str(ruleset["rules"]["costs"]["iva_rate_on_commission"]))
    )
    ranked = []
    for trial in case["trials"]:
        for row in trial["returns"]:
            session = date.fromisoformat(row["date"])
            if validation_start <= session <= validation_end:
                net = Decimal(str(row["gross_return"])) - Decimal(str(row["turnover"])) * fees
                ranked.append((abs(net), session, trial["trial_id"]))
    if not ranked:
        return {"status": "NOT_AVAILABLE", "reason": "no validation observations are available"}
    _, excluded_date, influential_trial = max(ranked, key=lambda item: (item[0], item[1], item[2]))
    perturbed = deepcopy(case)
    for trial in perturbed["trials"]:
        trial["returns"] = [row for row in trial["returns"] if row["date"] != excluded_date.isoformat()]
    try:
        sensitivity = evaluate_validation_case(perturbed, ruleset)
    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        return {
            "status": "NOT_AVAILABLE",
            "reason": f"one-session exclusion could not be evaluated: {type(exc).__name__}: {exc}",
            "excluded_validation_date": excluded_date.isoformat(),
            "influential_trial_id": influential_trial,
        }
    selected_before = result["selected_trial_id"]
    selected_after = sensitivity["selected_trial_id"]
    stable = selected_before == selected_after
    return {
        "status": "CHECKED" if stable else "FAILED",
        "reason": "validation-only largest-absolute-net-return session exclusion; final test untouched",
        "excluded_validation_date": excluded_date.isoformat(),
        "influential_trial_id": influential_trial,
        "selected_trial_before": selected_before,
        "selected_trial_after": selected_after,
        "selection_stable": stable,
    }


def _falsification_checks(
    hypothesis: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    case: Mapping[str, Any] | None,
    ruleset: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks = []
    for plan_check in hypothesis["falsification_plan"]:
        category = plan_check["category"]
        status = "NOT_AVAILABLE"
        reason = "required diagnostic is not present in the M4 result"
        details: dict[str, Any] = {}
        if result is not None:
            if category == "leakage":
                leakage = result["leakage_checks"]
                status = "CHECKED" if all(
                    leakage.get(key) is True
                    for key in ("chronological_non_overlapping_splits", "trial_return_dates_aligned", "selected_on_validation_only", "walk_forward_excludes_final_test")
                ) else "FAILED"
                reason = "M4 chronological, alignment, selection, and walk-forward guards"
                details = {
                    key: leakage.get(key)
                    for key in ("chronological_non_overlapping_splits", "trial_return_dates_aligned", "selected_on_validation_only", "walk_forward_excludes_final_test")
                }
            elif category == "regime":
                status = "CHECKED" if result["regime_splits"].get("status") == "PASS" else "NOT_AVAILABLE"
                reason = "caller-supplied test-period regime labels"
                details = {"status": result["regime_splits"].get("status"), "group_count": len(result["regime_splits"].get("groups", {}))}
            elif category == "parameter_sensitivity":
                status = "CHECKED" if result["parameter_sensitivity"].get("status") == "PASS" else "NOT_AVAILABLE"
                reason = "submitted parameter variants summarized on validation only"
                details = {"status": result["parameter_sensitivity"].get("status"), "parameter_count": len(result["parameter_sensitivity"].get("parameters", {}))}
            elif category == "costs":
                status = "CHECKED" if result["cost_sensitivity"] else "NOT_AVAILABLE"
                reason = "preregistered slippage sensitivity in M4"
                details = {"sensitivity_case_count": len(result["cost_sensitivity"])}
            elif category == "sample_size":
                diagnostics = result["sample_size_diagnostics"]
                status = "INSUFFICIENT" if diagnostics.get("small_test_sample") else "CHECKED"
                reason = f"test sessions={diagnostics.get('test_sessions')}"
                details = dict(diagnostics)
            elif category == "multiple_testing":
                diagnostics = (result["pbo"].get("status"), result["deflated_sharpe_ratio"].get("status"))
                status = "CHECKED" if diagnostics == ("PASS", "PASS") else "NOT_AVAILABLE"
                reason = f"PBO={diagnostics[0]}; DSR={diagnostics[1]}"
                details = {"pbo_status": diagnostics[0], "dsr_status": diagnostics[1]}
            elif category == "outliers":
                if case is not None:
                    sensitivity = _validation_outlier_sensitivity(case, ruleset, result)
                    status = sensitivity.pop("status")
                    reason = sensitivity.pop("reason")
                    details = sensitivity
                else:
                    status = "NOT_AVAILABLE"
                    reason = "M4 evaluation did not complete"
            elif category == "liquidity":
                status = "NOT_AVAILABLE"
                reason = "M4 input has portfolio returns/turnover but no instrument-level liquidity observations"
                details = {"available": ["aggregate_turnover"], "missing": ["instrument_id", "market_volume", "bid_ask"]}
        checks.append(
            {
                "category": category,
                "required": plan_check["required"],
                "status": status,
                "approach": plan_check["approach"],
                "reason": reason,
                "details": details,
            }
        )
    return checks


def run_registered_batch(
    plan: Any,
    *,
    plan_path: Path,
    ledger_path: Path,
    identity: Mapping[str, Any],
    ruleset: Mapping[str, Any],
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Evaluate every preregistered case and append results, including run failures."""
    normalized = validate_plan(plan)
    identity = _validate_code_identity(dict(identity), "code_identity")
    digest = hashlib.sha256(_canonical(normalized)).hexdigest()
    records = _read_ledger(ledger_path)
    registration = next(
        (record for record in records if record["event_type"] == "plan_registered" and record["batch_id"] == normalized["batch_id"]),
        None,
    )
    if registration is None:
        raise ResearchFactoryError("batch must be preregistered before it can run")
    if registration["plan_sha256"] != digest or registration["plan"] != normalized:
        raise ResearchFactoryError("batch plan differs from the preregistered plan")
    if registration["code_identity"] != identity:
        raise ResearchFactoryError("code identity changed after preregistration; create a new batch")
    completed = _utc(now_utc or datetime.now(timezone.utc).isoformat(), "completed_at_utc")
    if datetime.fromisoformat(completed) < datetime.fromisoformat(registration["created_at_utc"]):
        raise ResearchFactoryError("batch completion time cannot precede its preregistration")
    if any(record["event_type"] == "batch_completed" and record["batch_id"] == normalized["batch_id"] for record in records):
        raise ResearchFactoryError("batch already has a completed result record")
    plan_path = plan_path.resolve()
    prepared_by_index = []
    registered_experiments = registration["registered_experiments"]
    for index, item in enumerate(normalized["experiments"]):
        try:
            prepared_by_index.append(_read_registered_inputs({"experiments": [item]}, plan_path)[0])
        except (ResearchFactoryError, OSError, ValueError) as exc:
            prepared_by_index.append(
                {
                    "experiment_id": registered_experiments[index]["experiment_id"],
                    "hypothesis_id": registered_experiments[index]["hypothesis_id"],
                    "hypothesis_path": item["hypothesis_path"],
                    "hypothesis_sha256": item["hypothesis_sha256"],
                    "validation_case_path": item["validation_case_path"],
                    "validation_case_sha256": item["validation_case_sha256"],
                    "input_error": str(exc),
                    "hypothesis": None,
                    "case": None,
                }
            )
    results = []
    for prepared in prepared_by_index:
        if prepared.get("input_error"):
            error = prepared["input_error"]
            outcome = {
                "hypothesis_id": prepared["hypothesis_id"],
                "experiment_id": prepared["experiment_id"],
                "hypothesis_path": prepared["hypothesis_path"],
                "hypothesis_sha256": prepared["hypothesis_sha256"],
                "validation_case_path": prepared["validation_case_path"],
                "validation_case_sha256": prepared["validation_case_sha256"],
                "run_status": "RUN_ERROR",
                "m4_decision": None,
                "scientific_decision": "NEEDS_MORE_EVIDENCE",
                "m5_gate_downgraded": False,
                "decision_reasons": ["registered input changed or is unavailable"],
                "falsification_checks": [],
                "validation_result": None,
                "error": error,
            }
            results.append(outcome)
            continue
        try:
            cost_model = prepared["experiment_spec"]["transaction_cost_model"]
            active_costs = ruleset["rules"]["costs"]
            if cost_model["ruleset_id"] != ruleset["ruleset_id"]:
                raise ResearchFactoryError("ExperimentSpec ruleset_id differs from the active M1 rules")
            if Decimal(cost_model["commission_rate"]) != Decimal(str(active_costs["commission_rate"])):
                raise ResearchFactoryError("ExperimentSpec commission rate differs from the active M1 rules")
            if Decimal(cost_model["iva_rate_on_commission"]) != Decimal(str(active_costs["iva_rate_on_commission"])):
                raise ResearchFactoryError("ExperimentSpec IVA rate differs from the active M1 rules")
            validation_result = evaluate_validation_case(prepared["case"], ruleset)
            checks = _falsification_checks(prepared["hypothesis"], validation_result, prepared["case"], ruleset)
            m4_decision = validation_result["status_decision"]
            decision = m4_decision
            reasons = list(validation_result["decision_reasons"])
            missing_checks = [check["category"] for check in checks if check["required"] and check["status"] != "CHECKED"]
            evidence = validation_result["evidence_status"]
            downgraded = decision == "PROMOTE" and (
                evidence != "authorized_point_in_time"
                or validation_result["evidence_gaps"]
                or missing_checks
                or identity["working_tree_dirty"]
            )
            if downgraded:
                decision = "NEEDS_MORE_EVIDENCE"
                reasons.append("M5 research gate withheld promotion because required provenance/falsification evidence is incomplete")
                if missing_checks:
                    reasons.append("required falsification checks unavailable: " + ", ".join(missing_checks))
                if identity["working_tree_dirty"]:
                    reasons.append("execution-relevant working tree was dirty at preregistration/run time")
            outcome = {
                "hypothesis_id": prepared["hypothesis_id"],
                "experiment_id": prepared["experiment_id"],
                "hypothesis_path": prepared["hypothesis_path"],
                "hypothesis_sha256": prepared["hypothesis_sha256"],
                "validation_case_path": prepared["validation_case_path"],
                "validation_case_sha256": prepared["validation_case_sha256"],
                "run_status": "COMPLETED",
                "m4_decision": m4_decision,
                "scientific_decision": decision,
                "m5_gate_downgraded": downgraded,
                "decision_reasons": reasons,
                "falsification_checks": checks,
                "validation_result": validation_result,
                "error": None,
            }
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, ValueError, KeyError, TypeError) as exc:
            outcome = {
                "hypothesis_id": prepared["hypothesis_id"],
                "experiment_id": prepared["experiment_id"],
                "hypothesis_path": prepared["hypothesis_path"],
                "hypothesis_sha256": prepared["hypothesis_sha256"],
                "validation_case_path": prepared["validation_case_path"],
                "validation_case_sha256": prepared["validation_case_sha256"],
                "run_status": "RUN_ERROR",
                "m4_decision": None,
                "scientific_decision": "NEEDS_MORE_EVIDENCE",
                "m5_gate_downgraded": False,
                "decision_reasons": ["registered experiment could not complete; failure preserved"],
                "falsification_checks": [],
                "validation_result": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(outcome)
    expected_ids = {item["experiment_id"] for item in registered_experiments}
    for result in results:
        _validate_experiment_result(result, expected_ids)
    body = _event_body(
        records=records,
        event_type="batch_completed",
        batch_id=normalized["batch_id"],
        completed_at_utc=completed,
        plan_sha256=digest,
        code_identity=dict(identity),
        results=results,
    )
    _append_event(ledger_path, body)
    return {"batch_id": normalized["batch_id"], "results": results, "ledger_record_sha256": hashlib.sha256(_canonical(body)).hexdigest()}


def verify_ledger(path: Path) -> dict[str, Any]:
    """Verify canonical JSON lines, schema versions, sequential ids, and hash chain."""
    records = _read_ledger(path)
    return {
        "status": "PASS",
        "record_count": len(records),
        "head_record_sha256": records[-1]["record_sha256"] if records else None,
    }


def list_promoted_experiments(path: Path) -> dict[str, Any]:
    """Return only the latest, verified M5 promotion for each hypothesis.

    A later decision for a hypothesis supersedes its earlier decision. The
    ledger's hash chain is tamper-evident, not an authenticated signature.
    """
    records = _read_ledger(path)
    latest_by_hypothesis: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for record in records:
        if record["event_type"] != "batch_completed":
            continue
        for result in record["results"]:
            latest_by_hypothesis[result["hypothesis_id"]] = (record, result)

    promoted = []
    seen_experiment_ids: set[str] = set()
    for record, result in latest_by_hypothesis.values():
        if (
            result["scientific_decision"] != "PROMOTE"
            or result["m5_gate_downgraded"]
            or result["run_status"] != "COMPLETED"
        ):
            continue
        if result["experiment_id"] in seen_experiment_ids:
            raise ResearchFactoryError(
                f"latest promoted decisions reuse experiment ID {result['experiment_id']!r}"
            )
        seen_experiment_ids.add(result["experiment_id"])
        registered = next(
            item
            for prior in records
            if prior["event_type"] == "plan_registered" and prior["batch_id"] == record["batch_id"]
            for item in prior["registered_experiments"]
            if item["experiment_id"] == result["experiment_id"]
        )
        promoted.append(
            {
                "experiment_id": result["experiment_id"],
                "hypothesis_id": result["hypothesis_id"],
                "promotion_record_sha256": record["record_sha256"],
                "scientific_decision": result["scientific_decision"],
                "m5_gate_downgraded": result["m5_gate_downgraded"],
                "experiment_spec": registered["experiment_spec"],
                "validation_result": result["validation_result"],
            }
        )
    promoted.sort(key=lambda item: item["experiment_id"])
    return {
        "status": "PASS",
        "ledger_head_record_sha256": records[-1]["record_sha256"] if records else None,
        "promoted_experiments": promoted,
        "promotion_count": len(promoted),
        "integrity_note": "Verified M5 hash chain; hash chain is not a signed or authenticated record.",
    }


def summarize_ledger(path: Path) -> dict[str, Any]:
    """Count registered/tested hypotheses and every final decision without dropping failures."""
    records = _read_ledger(path)
    registered_hypotheses = set()
    registered_experiments = 0
    tested_hypotheses = set()
    completed_experiments = 0
    run_errors = 0
    attempts = {decision: 0 for decision in sorted(_DECISIONS)}
    latest_by_hypothesis: dict[str, str] = {}
    for record in records:
        body = {key: value for key, value in record.items() if key != "record_sha256"}
        if body["event_type"] == "plan_registered":
            registered_experiments += len(body["plan"]["experiments"])
            # IDs live inside hashed hypothesis files; record them during registration for self-contained counts.
            for experiment in body["registered_experiments"]:
                registered_hypotheses.add(experiment["hypothesis_id"])
        else:
            for result in body["results"]:
                tested_hypotheses.add(result["hypothesis_id"])
                attempts[result["scientific_decision"]] += 1
                latest_by_hypothesis[result["hypothesis_id"]] = result["scientific_decision"]
                if result["run_status"] == "RUN_ERROR":
                    run_errors += 1
                else:
                    completed_experiments += 1
    latest_counts = {decision: 0 for decision in sorted(_DECISIONS)}
    for decision in latest_by_hypothesis.values():
        latest_counts[decision] += 1
    return {
        "status": "PASS",
        "batch_count_registered": sum(record["event_type"] == "plan_registered" for record in records),
        "batch_count_completed": sum(record["event_type"] == "batch_completed" for record in records),
        "hypotheses_registered": len(registered_hypotheses),
        "hypotheses_tested": len(tested_hypotheses),
        "experiments_registered": registered_experiments,
        "experiments_completed": completed_experiments,
        "run_errors": run_errors,
        "decision_attempt_counts": attempts,
        "latest_hypothesis_decisions": latest_counts,
        "latest_decision_by_hypothesis": dict(sorted(latest_by_hypothesis.items())),
    }


__all__ = [
    "ResearchFactoryError",
    "code_identity",
    "list_promoted_experiments",
    "load_plan",
    "register_plan",
    "run_registered_batch",
    "summarize_ledger",
    "validate_plan",
    "verify_ledger",
]
