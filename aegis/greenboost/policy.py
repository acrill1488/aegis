"""Pure policy evaluation for immutable GreenBoost resource snapshots."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Self

from pydantic import Field, field_validator, model_validator

from .contracts import ContractModel, NodeReference, ResourceSnapshot


class PolicyOperator(StrEnum):
    """Closed set of safe resource-rule operators."""

    less_than = "less_than"
    less_than_or_equal = "less_than_or_equal"
    greater_than = "greater_than"
    greater_than_or_equal = "greater_than_or_equal"
    equal = "equal"
    not_equal = "not_equal"
    is_true = "is_true"
    is_false = "is_false"


class PolicyOutcome(StrEnum):
    """Policy-oriented result without admission semantics."""

    passed = "pass"
    failed = "fail"
    unknown = "unknown"
    not_applicable = "not_applicable"


class PolicySeverity(StrEnum):
    """Importance reported for a failed or unknown rule."""

    info = "info"
    warning = "warning"
    critical = "critical"


class ResourceMetric(StrEnum):
    """Metrics canonically extractable from ``ResourceSnapshot``."""

    cpu_utilization_percent = "cpu_utilization_percent"
    ram_used_mb = "ram_used_mb"
    ram_available_mb = "ram_available_mb"
    ram_utilization_percent = "ram_utilization_percent"
    gpu_count = "gpu_count"
    vram_used_mb = "vram_used_mb"
    vram_available_mb = "vram_available_mb"
    vram_utilization_percent = "vram_utilization_percent"
    disk_used_mb = "disk_used_mb"
    disk_available_mb = "disk_available_mb"
    disk_utilization_percent = "disk_utilization_percent"
    docker_available = "docker_available"
    ollama_available = "ollama_available"
    ocr_available = "ocr_available"
    comfyui_available = "comfyui_available"
    embedding_available = "embedding_available"
    remote_available = "remote_available"


_NUMERIC_OPERATORS = frozenset(
    {
        PolicyOperator.less_than,
        PolicyOperator.less_than_or_equal,
        PolicyOperator.greater_than,
        PolicyOperator.greater_than_or_equal,
        PolicyOperator.equal,
        PolicyOperator.not_equal,
    }
)
_BOOLEAN_OPERATORS = frozenset({PolicyOperator.is_true, PolicyOperator.is_false})
_BOOLEAN_METRICS = frozenset(
    {
        ResourceMetric.docker_available,
        ResourceMetric.ollama_available,
        ResourceMetric.ocr_available,
        ResourceMetric.comfyui_available,
        ResourceMetric.embedding_available,
        ResourceMetric.remote_available,
    }
)


class PolicyRule(ContractModel):
    """One validated resource constraint."""

    id: str = Field(min_length=1, max_length=128)
    metric: ResourceMetric
    operator: PolicyOperator
    threshold: float | None = None
    severity: PolicySeverity = PolicySeverity.warning
    enabled: bool = True
    description: str = Field(default="", max_length=2048)

    @field_validator("id")
    @classmethod
    def reject_blank_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rule id must not be blank")
        return value

    @field_validator("threshold", mode="before")
    @classmethod
    def validate_threshold_type(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("numeric threshold must not be a boolean")
        return value

    @model_validator(mode="after")
    def validate_operator_and_threshold(self) -> Self:
        if self.operator in _NUMERIC_OPERATORS:
            if self.metric in _BOOLEAN_METRICS:
                raise ValueError("numeric operators require a numeric metric")
            if self.threshold is None or not isfinite(self.threshold):
                raise ValueError("numeric operators require a finite numeric threshold")
        elif self.operator in _BOOLEAN_OPERATORS:
            if self.metric not in _BOOLEAN_METRICS:
                raise ValueError("boolean operators require a boolean metric")
            if self.threshold is not None:
                raise ValueError("boolean operators must not define a threshold")
        return self


class ResourcePolicy(ContractModel):
    """Ordered immutable collection of resource constraints."""

    id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2048)
    enabled: bool = True
    rules: tuple[PolicyRule, ...] = ()

    @field_validator("id", "version")
    @classmethod
    def reject_blank_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy id and version must not be blank")
        return value

    @model_validator(mode="after")
    def reject_duplicate_rule_ids(self) -> Self:
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rule ids are forbidden")
        return self


class PolicyRuleResult(ContractModel):
    """Complete immutable evidence for one evaluated rule."""

    policy_id: str
    rule_id: str
    metric: ResourceMetric
    operator: PolicyOperator
    expected_value: float | bool
    observed_value: float | int | bool | None
    outcome: PolicyOutcome
    severity: PolicySeverity
    message: str
    reason_code: str | None = None


class PolicyEvaluation(ContractModel):
    """Ordered immutable policy summary for one resource snapshot."""

    policy_id: str
    policy_version: str
    snapshot_timestamp: datetime
    node: NodeReference
    results: tuple[PolicyRuleResult, ...]
    total_rule_count: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    overall_outcome: PolicyOutcome


NumericValue = float | int
MetricValue = NumericValue | bool | None
MetricExtractor = Callable[[ResourceSnapshot], MetricValue]


def _utilization(used: int | None, total: int | None) -> float | None:
    if used is None or total is None or total <= 0:
        return None
    return used / total * 100


def _vram_total(snapshot: ResourceSnapshot, field: str) -> int | None:
    values = [
        value
        for gpu in snapshot.gpus
        if (value := getattr(gpu.vram, field)) is not None
    ]
    return sum(values) if values else None


def _vram_utilization(snapshot: ResourceSnapshot) -> float | None:
    used = _vram_total(snapshot, "used_mb")
    available = _vram_total(snapshot, "available_mb")
    if used is None or available is None or used + available <= 0:
        return None
    return used / (used + available) * 100


def _service_available(
    snapshot: ResourceSnapshot, ids: frozenset[str], prefixes: tuple[str, ...] = ()
) -> bool | None:
    matching = [
        service.reachable
        for service in snapshot.services
        if service.id in ids or service.id.startswith(prefixes)
    ]
    known = [value for value in matching if value is not None]
    if any(known):
        return True
    if known:
        return False
    return None


_SERVICE_IDENTITIES = {
    ResourceMetric.docker_available: (frozenset({"docker"}), ()),
    ResourceMetric.ollama_available: (frozenset({"ollama"}), ()),
    ResourceMetric.ocr_available: (frozenset({"unlimited-ocr", "paddleocr"}), ()),
    ResourceMetric.comfyui_available: (frozenset({"comfyui"}), ()),
    ResourceMetric.embedding_available: (frozenset({"bge-m3", "bge_m3"}), ()),
    ResourceMetric.remote_available: (frozenset(), ("remote-runtime:",)),
}


_METRIC_EXTRACTORS: dict[ResourceMetric, MetricExtractor] = {
    ResourceMetric.cpu_utilization_percent: lambda snapshot: snapshot.cpu.utilization_percent,
    ResourceMetric.ram_used_mb: lambda snapshot: snapshot.ram.used_mb,
    ResourceMetric.ram_available_mb: lambda snapshot: snapshot.ram.available_mb,
    ResourceMetric.ram_utilization_percent: lambda snapshot: _utilization(
        snapshot.ram.used_mb, snapshot.ram.total_mb
    ),
    ResourceMetric.gpu_count: lambda snapshot: len(snapshot.gpus),
    ResourceMetric.vram_used_mb: lambda snapshot: _vram_total(snapshot, "used_mb"),
    ResourceMetric.vram_available_mb: lambda snapshot: _vram_total(snapshot, "available_mb"),
    ResourceMetric.vram_utilization_percent: _vram_utilization,
    ResourceMetric.disk_used_mb: lambda snapshot: snapshot.disk.used_mb,
    ResourceMetric.disk_available_mb: lambda snapshot: snapshot.disk.available_mb,
    ResourceMetric.disk_utilization_percent: lambda snapshot: _utilization(
        snapshot.disk.used_mb, snapshot.disk.total_mb
    ),
    **{
        metric: lambda snapshot, identity=identity: _service_available(snapshot, *identity)
        for metric, identity in _SERVICE_IDENTITIES.items()
    },
}


_COMPARATORS: dict[PolicyOperator, Callable[[NumericValue, float], bool]] = {
    PolicyOperator.less_than: lambda observed, expected: observed < expected,
    PolicyOperator.less_than_or_equal: lambda observed, expected: observed <= expected,
    PolicyOperator.greater_than: lambda observed, expected: observed > expected,
    PolicyOperator.greater_than_or_equal: lambda observed, expected: observed >= expected,
    PolicyOperator.equal: lambda observed, expected: observed == expected,
    PolicyOperator.not_equal: lambda observed, expected: observed != expected,
}


class PolicyEngine:
    """Stateless evaluator with no admission, I/O, history, or caching behavior."""

    __slots__ = ()

    def evaluate(
        self, policy: ResourcePolicy, snapshot: ResourceSnapshot
    ) -> PolicyEvaluation:
        """Evaluate all rules in order and summarize by fail/unknown/pass/N-A precedence."""

        results = tuple(self._evaluate_rule(policy, rule, snapshot) for rule in policy.rules)
        counts = {outcome: 0 for outcome in PolicyOutcome}
        for result in results:
            counts[result.outcome] += 1
        if counts[PolicyOutcome.failed]:
            overall = PolicyOutcome.failed
        elif counts[PolicyOutcome.unknown]:
            overall = PolicyOutcome.unknown
        elif counts[PolicyOutcome.passed]:
            overall = PolicyOutcome.passed
        else:
            overall = PolicyOutcome.not_applicable
        return PolicyEvaluation(
            policy_id=policy.id,
            policy_version=policy.version,
            snapshot_timestamp=snapshot.timestamp,
            node=snapshot.node,
            results=results,
            total_rule_count=len(results),
            pass_count=counts[PolicyOutcome.passed],
            fail_count=counts[PolicyOutcome.failed],
            unknown_count=counts[PolicyOutcome.unknown],
            not_applicable_count=counts[PolicyOutcome.not_applicable],
            overall_outcome=overall,
        )

    def evaluate_many(
        self, policies: tuple[ResourcePolicy, ...], snapshot: ResourceSnapshot
    ) -> tuple[PolicyEvaluation, ...]:
        """Evaluate multiple independent policies in declared order."""

        return tuple(self.evaluate(policy, snapshot) for policy in policies)

    @staticmethod
    def _evaluate_rule(
        policy: ResourcePolicy, rule: PolicyRule, snapshot: ResourceSnapshot
    ) -> PolicyRuleResult:
        expected: float | bool = (
            rule.operator is PolicyOperator.is_true
            if rule.operator in _BOOLEAN_OPERATORS
            else rule.threshold  # type: ignore[assignment]
        )
        if not policy.enabled:
            observed = None
            outcome = PolicyOutcome.not_applicable
            reason = "policy_disabled"
        elif not rule.enabled:
            observed = None
            outcome = PolicyOutcome.not_applicable
            reason = "rule_disabled"
        else:
            observed = _METRIC_EXTRACTORS[rule.metric](snapshot)
            if observed is None:
                outcome = PolicyOutcome.unknown
                reason = "metric_unavailable"
            elif rule.operator in _BOOLEAN_OPERATORS:
                outcome = (
                    PolicyOutcome.passed
                    if observed is expected
                    else PolicyOutcome.failed
                )
                reason = None if outcome is PolicyOutcome.passed else "constraint_violated"
            else:
                matches = _COMPARATORS[rule.operator](observed, rule.threshold)  # type: ignore[arg-type]
                outcome = PolicyOutcome.passed if matches else PolicyOutcome.failed
                reason = None if matches else "constraint_violated"
        message = rule.description or f"{rule.metric.value} {outcome.value}"
        return PolicyRuleResult(
            policy_id=policy.id,
            rule_id=rule.id,
            metric=rule.metric,
            operator=rule.operator,
            expected_value=expected,
            observed_value=observed,
            outcome=outcome,
            severity=rule.severity,
            message=message,
            reason_code=reason,
        )
