"""Small, explicitly validated M0 projections of the architecture contracts."""

from dataclasses import MISSING, asdict, dataclass, field, fields
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _json_values(value: Any) -> None:
    if isinstance(value, dict):
        require(all(type(key) is str for key in value), "JSON keys must be strings")
        for item in value.values():
            _json_values(item)
    elif isinstance(value, list):
        for item in value:
            _json_values(item)
    else:
        require(type(value) in (str, int, float, bool, type(None)), "Invalid JSON value")
        if type(value) is float:
            require(math.isfinite(value), "Non-finite JSON number")


def canonical_json(value: Any) -> bytes:
    """UTF-8, sorted string keys, compact separators and one final newline."""
    _json_values(value)
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def load_json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"),
                       parse_constant=_invalid_constant, object_pairs_hook=_unique_object)
    _json_values(value)
    return value


def _field_values(model: type, value: Any, exclude: set[str] | None = None) -> dict:
    require(type(value) is dict, f"{model.__name__} must be an object")
    descriptors = [item for item in fields(model) if item.name not in (exclude or set())]
    allowed = {item.name for item in descriptors}
    mandatory = {item.name for item in descriptors
                 if item.default is MISSING and item.default_factory is MISSING}
    require(mandatory <= value.keys(), f"Missing fields: {sorted(mandatory - value.keys())}")
    require(value.keys() <= allowed, f"Unknown fields: {sorted(value.keys() - allowed)}")
    return value


def _text(value: Any, name: str) -> None:
    require(type(value) is str and bool(value.strip()), f"{name} must be nonempty text")


def validate_commit(value: Any) -> None:
    require(value is None or (type(value) is str and
                             re.fullmatch(r"[0-9a-f]{40}", value) is not None),
            "commit_sha must be null or a full lowercase Git SHA")


def _null_fields(value: Any, names: tuple[str, ...]) -> None:
    for name in names:
        require(getattr(value, name) is None, f"{name} is not applicable in M0")


@dataclass(frozen=True)
class ExperimentSpec:
    schema_version: int
    experiment_id: str
    hypothesis: str
    dataset_version: str
    universe_version: None
    parameters: dict[str, int]
    benchmark: dict[str, list[int]]
    seed: int
    commit_sha: str | None
    strategy_family: None = None
    features: list = field(default_factory=list)
    target: str = "integer_sum"
    horizon: None = None
    train_period: None = None
    validation_period: None = None
    test_period: None = None
    transaction_cost_model: None = None
    execution_model: None = None
    promotion_criteria: None = None

    def __post_init__(self) -> None:
        require(type(self.schema_version) is int and self.schema_version == 1,
                "Unsupported spec schema_version")
        require(self.experiment_id == "HARNESS_SMOKE_001", "Unsupported experiment_id")
        _text(self.hypothesis, "hypothesis")
        require(self.dataset_version == "synthetic_arithmetic_v1", "Unsupported dataset_version")
        require(type(self.seed) is int and self.seed >= 0, "seed must be a nonnegative integer")
        validate_commit(self.commit_sha)
        require(type(self.parameters) is dict and
                self.parameters.keys() == {"sample_count", "modulus"}, "Invalid parameters")
        count, modulus = self.parameters["sample_count"], self.parameters["modulus"]
        require(type(count) is int and 1 <= count <= 64, "sample_count must be in [1, 64]")
        require(type(modulus) is int and modulus >= 2, "modulus must be an integer >= 2")
        require(type(self.benchmark) is dict and self.benchmark.keys() == {"expected_values"},
                "Invalid benchmark")
        expected = self.benchmark["expected_values"]
        require(type(expected) is list and len(expected) == count and
                all(type(item) is int and 0 <= item < modulus for item in expected),
                "expected_values must match sample_count and modulus")
        require(type(self.features) is list and not self.features, "features must be empty in M0")
        require(self.target == "integer_sum", "Unsupported target")
        _null_fields(self, ("universe_version", "strategy_family", "horizon", "train_period",
                           "validation_period", "test_period", "transaction_cost_model",
                           "execution_model", "promotion_criteria"))

    @classmethod
    def from_dict(cls, value: Any) -> "ExperimentSpec":
        return cls(**_field_values(cls, value))

    def to_dict(self) -> dict:
        self.__post_init__()
        return asdict(self)

    @property
    def config_sha256(self) -> str:
        config = self.to_dict()
        del config["commit_sha"]
        return hashlib.sha256(canonical_json(config)).hexdigest()


@dataclass(frozen=True)
class ExperimentResult:
    schema_version: int
    experiment_id: str
    dataset_version: str
    universe_version: None
    seed: int
    config_sha256: str
    code_sha256: str
    status: str
    values: list[int]
    metrics: dict[str, int]
    failure_reason: str | None
    execution: dict[str, Any]
    in_sample_metrics: None = None
    validation_metrics: None = None
    out_of_sample_metrics: None = None
    cost_adjusted_metrics: None = None
    turnover: None = None
    drawdown: None = None
    bootstrap_results: None = None
    stability_results: None = None
    leakage_checks: None = None
    multiple_testing_context: None = None
    promotion_status: None = None
    rejection_reason: None = None
    artifacts: list[str] = field(default_factory=lambda: ["resolved_spec.json", "payload.json"])

    def __post_init__(self) -> None:
        require(type(self.schema_version) is int and self.schema_version == 1,
                "Unsupported result schema_version")
        require(self.experiment_id == "HARNESS_SMOKE_001", "Unsupported experiment_id")
        require(self.dataset_version == "synthetic_arithmetic_v1", "Unsupported dataset_version")
        require(type(self.seed) is int and self.seed >= 0, "Invalid result seed")
        for name in ("config_sha256", "code_sha256"):
            digest = getattr(self, name)
            require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                    f"Invalid {name}")
        require(self.status in ("PASS", "FAIL"), "status must be PASS or FAIL")
        require(type(self.values) is list and 1 <= len(self.values) <= 64 and
                all(type(item) is int and item >= 0 for item in self.values), "Invalid values")
        require(type(self.metrics) is dict and self.metrics.keys() ==
                {"sample_count", "integer_sum", "reference_check", "deterministic_check"},
                "Invalid metrics")
        require(all(type(item) is int for item in self.metrics.values()), "Metrics must be integers")
        require(self.metrics["sample_count"] == len(self.values) and
                self.metrics["integer_sum"] == sum(self.values), "Inconsistent metrics")
        checks = (self.metrics["reference_check"], self.metrics["deterministic_check"])
        require(all(item in (0, 1) for item in checks), "Invalid check metrics")
        if self.status == "PASS":
            require(checks == (1, 1) and self.failure_reason is None, "Inconsistent PASS")
        else:
            require(checks != (1, 1), "FAIL must identify a failed check")
            _text(self.failure_reason, "failure_reason")
        require(self.artifacts == ["resolved_spec.json", "payload.json"], "Invalid artifact references")
        _null_fields(self, ("universe_version", "in_sample_metrics", "validation_metrics",
                           "out_of_sample_metrics", "cost_adjusted_metrics", "turnover",
                           "drawdown", "bootstrap_results", "stability_results", "leakage_checks",
                           "multiple_testing_context", "promotion_status", "rejection_reason"))
        require(type(self.execution) is dict and self.execution.keys() ==
                {"commit_sha", "working_tree_dirty", "python_version", "package_version",
                 "timestamp_utc", "run_id"}, "Invalid execution metadata")
        validate_commit(self.execution["commit_sha"])
        require(type(self.execution["working_tree_dirty"]) in (bool, type(None)),
                "working_tree_dirty must be boolean or null")
        for name in ("python_version", "package_version", "timestamp_utc"):
            _text(self.execution[name], name)
        require(datetime.fromisoformat(self.execution["timestamp_utc"]).utcoffset() == timedelta(0),
                "timestamp_utc must include UTC timezone")
        if self.execution["run_id"] is not None:
            _text(self.execution["run_id"], "run_id")

    @classmethod
    def from_dict(cls, value: Any) -> "ExperimentResult":
        require(type(value) is dict and value.keys() == {"payload", "execution"},
                "Result must contain payload and execution")
        return cls(**_field_values(cls, value["payload"], {"execution"}),
                   execution=value["execution"])

    @property
    def payload(self) -> dict:
        self.__post_init__()
        data = asdict(self)
        del data["execution"]
        return data

    def to_dict(self) -> dict:
        return {"payload": self.payload, "execution": dict(self.execution)}
