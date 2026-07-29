"""Stateless admission decisions over immutable GreenBoost evidence.

Current admission service availability follows canonical snapshot reachability;
future lifecycle stages may distinguish reachable, healthy, ready, busy, and
degraded states.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Self

from pydantic import Field, field_validator, model_validator

from .contracts import ContractModel, NodeReference, ResourceSnapshot
from .ledger import ResourceStatistics
from .policy import (
    PolicyEvaluation,
    PolicyOutcome,
    PolicyRuleResult,
    PolicySeverity,
)


class AdmissionOutcome(StrEnum):
    """Immediate disposition of one execution resource request."""

    allow = "allow"
    deny = "deny"
    wait = "wait"
    degraded = "degraded"


class AdmissionReasonCode(StrEnum):
    """Stable machine-readable admission diagnostics."""

    admitted = "admitted"
    policy_failed = "policy_failed"
    policy_unknown = "policy_unknown"
    policy_not_applicable = "policy_not_applicable"
    insufficient_cpu = "insufficient_cpu"
    insufficient_ram = "insufficient_ram"
    insufficient_vram = "insufficient_vram"
    insufficient_disk = "insufficient_disk"
    missing_gpu = "missing_gpu"
    service_unavailable = "service_unavailable"
    service_unknown = "service_unknown"
    snapshot_stale = "snapshot_stale"
    statistics_unavailable = "statistics_unavailable"
    degraded_requirement_used = "degraded_requirement_used"
    request_invalid = "request_invalid"
    no_applicable_policy = "no_applicable_policy"


class ResourceRequirement(ContractModel):
    """Strict and explicitly permitted degraded resource requirements."""

    minimum_cpu_available_percent: float | None = Field(default=None, ge=0, le=100)
    minimum_ram_available_mb: float | None = Field(default=None, ge=0)
    minimum_vram_available_mb: float | None = Field(default=None, ge=0)
    minimum_disk_available_mb: float | None = Field(default=None, ge=0)
    minimum_gpu_count: int = Field(default=0, ge=0)
    required_services: tuple[str, ...] = ()
    allow_degraded: bool = False
    degraded_ram_available_mb: float | None = Field(default=None, ge=0)
    degraded_vram_available_mb: float | None = Field(default=None, ge=0)
    degraded_gpu_count: int | None = Field(default=None, ge=0)

    @field_validator(
        "minimum_cpu_available_percent",
        "minimum_ram_available_mb",
        "minimum_vram_available_mb",
        "minimum_disk_available_mb",
        "minimum_gpu_count",
        "degraded_ram_available_mb",
        "degraded_vram_available_mb",
        "degraded_gpu_count",
        mode="before",
    )
    @classmethod
    def reject_invalid_number(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("resource requirements must not be booleans")
        if isinstance(value, (int, float)) and not isfinite(value):
            raise ValueError("resource requirements must be finite")
        return value

    @field_validator("required_services", mode="before")
    @classmethod
    def normalize_services(cls, value: object) -> object:
        if value is None:
            return ()
        services = tuple(str(item).strip().casefold() for item in value)  # type: ignore[arg-type]
        if any(not item for item in services):
            raise ValueError("required service ids must not be blank")
        if len(services) != len(set(services)):
            raise ValueError("duplicate required services are forbidden")
        return services

    @model_validator(mode="after")
    def validate_degraded_requirements(self) -> Self:
        pairs = (
            ("degraded_ram_available_mb", "minimum_ram_available_mb"),
            ("degraded_vram_available_mb", "minimum_vram_available_mb"),
            ("degraded_gpu_count", "minimum_gpu_count"),
        )
        degraded_values = [getattr(self, degraded) for degraded, _ in pairs]
        if any(value is not None for value in degraded_values) and not self.allow_degraded:
            raise ValueError("degraded requirements require allow_degraded=True")
        for degraded_name, strict_name in pairs:
            degraded = getattr(self, degraded_name)
            strict = getattr(self, strict_name)
            if degraded is not None and (strict is None or degraded > strict):
                raise ValueError(f"{degraded_name} cannot exceed {strict_name}")
        return self


class AdmissionRequest(ContractModel):
    """Immutable admission identity, requirements, and precomputed policy evidence."""

    id: str = Field(min_length=1, max_length=256)
    created_at: datetime
    requirement: ResourceRequirement = Field(default_factory=ResourceRequirement)
    policy_evaluations: tuple[PolicyEvaluation, ...] = ()
    maximum_snapshot_age_seconds: float | None = Field(default=None, ge=0)

    @field_validator("id")
    @classmethod
    def reject_blank_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("request id must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("maximum_snapshot_age_seconds", mode="before")
    @classmethod
    def validate_snapshot_age(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("maximum snapshot age must not be a boolean")
        if isinstance(value, (int, float)) and not isfinite(value):
            raise ValueError("maximum snapshot age must be finite")
        return value

    @model_validator(mode="after")
    def reject_duplicate_policy_evaluations(self) -> Self:
        identities = [
            (evaluation.policy_id, evaluation.policy_version)
            for evaluation in self.policy_evaluations
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate policy evaluation identities are forbidden")
        return self


class AdmissionReason(ContractModel):
    """Structured evidence supporting an admission decision."""

    code: AdmissionReasonCode
    message: str = Field(min_length=1, max_length=2048)
    mandatory: bool
    observed_value: float | int | bool | str | None = None
    required_value: float | int | bool | str | None = None
    policy_id: str | None = None
    rule_id: str | None = None
    service_id: str | None = None
    metric: str | None = None


class AdmissionDecision(ContractModel):
    """Serializable, immutable result of one stateless admission evaluation."""

    request_id: str
    outcome: AdmissionOutcome
    snapshot_timestamp: datetime
    node: NodeReference
    evaluated_at: datetime
    reasons: tuple[AdmissionReason, ...]
    policy_evaluation_count: int = Field(ge=0)
    mandatory_failure_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    degraded_requirement_used: bool


class _Disposition(StrEnum):
    allow = "allow"
    deny = "deny"
    wait = "wait"
    degraded = "degraded"


class AdmissionController:
    """Pure controller consuming policy results and current snapshot evidence."""

    __slots__ = ()

    def evaluate(
        self,
        request: AdmissionRequest,
        snapshot: ResourceSnapshot,
        statistics: ResourceStatistics | None = None,
        evaluated_at: datetime | None = None,
    ) -> AdmissionDecision:
        """Return deny > wait > degraded > allow without retaining any state.

        Statistics are deliberately accepted but unused until a canonical trend
        rule or request requirement is defined. The ledger is never accessed.
        """

        del statistics
        when = _utc_now() if evaluated_at is None else _aware_utc(evaluated_at)
        reasons: list[AdmissionReason] = []
        dispositions: list[_Disposition] = []

        if request.maximum_snapshot_age_seconds is not None:
            age = (when - snapshot.timestamp).total_seconds()
            if age < 0 or age > request.maximum_snapshot_age_seconds:
                reasons.append(
                    AdmissionReason(
                        code=AdmissionReasonCode.snapshot_stale,
                        message=(
                            "snapshot timestamp is in the future"
                            if age < 0
                            else "snapshot exceeds the requested maximum age"
                        ),
                        mandatory=True,
                        observed_value=age,
                        required_value=request.maximum_snapshot_age_seconds,
                        metric="snapshot_age_seconds",
                    )
                )
                dispositions.append(_Disposition.wait)

        policy_dispositions, applicable = _evaluate_policies(
            request.policy_evaluations, reasons, request.requirement
        )
        dispositions.extend(policy_dispositions)
        if not applicable:
            reasons.append(
                AdmissionReason(
                    code=AdmissionReasonCode.no_applicable_policy,
                    message="no applicable policy result was provided",
                    mandatory=False,
                )
            )

        if not dispositions or _Disposition.wait not in dispositions or not any(
            reason.code is AdmissionReasonCode.snapshot_stale for reason in reasons
        ):
            dispositions.extend(_evaluate_resources(request.requirement, snapshot, reasons))

        outcome = _aggregate(dispositions)
        if not reasons:
            reasons.append(
                AdmissionReason(
                    code=AdmissionReasonCode.admitted,
                    message="all admission requirements passed",
                    mandatory=False,
                )
            )
        return AdmissionDecision(
            request_id=request.id,
            outcome=outcome,
            snapshot_timestamp=snapshot.timestamp,
            node=snapshot.node,
            evaluated_at=when,
            reasons=tuple(reasons),
            policy_evaluation_count=len(request.policy_evaluations),
            mandatory_failure_count=sum(
                reason.mandatory
                and reason.code
                in {
                    AdmissionReasonCode.policy_failed,
                    AdmissionReasonCode.insufficient_cpu,
                    AdmissionReasonCode.insufficient_ram,
                    AdmissionReasonCode.insufficient_vram,
                    AdmissionReasonCode.insufficient_disk,
                    AdmissionReasonCode.missing_gpu,
                    AdmissionReasonCode.service_unavailable,
                }
                for reason in reasons
            ),
            unknown_count=sum(
                reason.code
                in {
                    AdmissionReasonCode.policy_unknown,
                    AdmissionReasonCode.service_unknown,
                    AdmissionReasonCode.snapshot_stale,
                }
                or (reason.observed_value is None and reason.mandatory)
                for reason in reasons
            ),
            degraded_requirement_used=outcome is AdmissionOutcome.degraded,
        )


def _evaluate_policies(
    evaluations: tuple[PolicyEvaluation, ...],
    reasons: list[AdmissionReason],
    requirement: ResourceRequirement,
) -> tuple[list[_Disposition], bool]:
    dispositions: list[_Disposition] = []
    applicable = False
    for evaluation in evaluations:
        for result in evaluation.results:
            if result.outcome is PolicyOutcome.passed:
                applicable = True
                continue
            if result.outcome is PolicyOutcome.not_applicable:
                reasons.append(_policy_reason(result, AdmissionReasonCode.policy_not_applicable, False))
                continue
            applicable = True
            mandatory = result.severity is PolicySeverity.critical
            code = (
                AdmissionReasonCode.policy_failed
                if result.outcome is PolicyOutcome.failed
                else AdmissionReasonCode.policy_unknown
            )
            reasons.append(_policy_reason(result, code, mandatory))
            if result.severity is PolicySeverity.critical:
                dispositions.append(
                    _Disposition.deny
                    if result.outcome is PolicyOutcome.failed
                    else _Disposition.wait
                )
            elif (
                result.severity is PolicySeverity.warning
                and result.outcome is PolicyOutcome.failed
                and requirement.allow_degraded
            ):
                dispositions.append(_Disposition.degraded)
            elif (
                result.severity is PolicySeverity.warning
                and result.outcome is PolicyOutcome.unknown
                and _unknown_policy_is_degradable(result, requirement)
            ):
                dispositions.append(_Disposition.degraded)
    return dispositions, applicable


def _unknown_policy_is_degradable(
    result: PolicyRuleResult, requirement: ResourceRequirement
) -> bool:
    degraded_by_metric = {
        "ram_available_mb": requirement.degraded_ram_available_mb,
        "vram_available_mb": requirement.degraded_vram_available_mb,
        "gpu_count": requirement.degraded_gpu_count,
    }
    return requirement.allow_degraded and degraded_by_metric.get(result.metric.value) is not None


def _policy_reason(
    result: PolicyRuleResult, code: AdmissionReasonCode, mandatory: bool
) -> AdmissionReason:
    return AdmissionReason(
        code=code,
        message=result.message,
        mandatory=mandatory,
        observed_value=result.observed_value,
        required_value=result.expected_value,
        policy_id=result.policy_id,
        rule_id=result.rule_id,
        metric=result.metric.value,
    )


def _evaluate_resources(
    requirement: ResourceRequirement,
    snapshot: ResourceSnapshot,
    reasons: list[AdmissionReason],
) -> list[_Disposition]:
    dispositions: list[_Disposition] = []
    cpu = (
        None
        if snapshot.cpu.utilization_percent is None
        else 100 - snapshot.cpu.utilization_percent
    )
    _strict_only(
        "CPU availability",
        cpu,
        requirement.minimum_cpu_available_percent,
        AdmissionReasonCode.insufficient_cpu,
        "cpu_available_percent",
        reasons,
        dispositions,
    )
    _strict_or_degraded(
        "RAM availability",
        snapshot.ram.available_mb,
        requirement.minimum_ram_available_mb,
        requirement.degraded_ram_available_mb,
        AdmissionReasonCode.insufficient_ram,
        "ram_available_mb",
        reasons,
        dispositions,
    )
    _strict_or_degraded(
        "GPU count",
        len(snapshot.gpus),
        requirement.minimum_gpu_count,
        requirement.degraded_gpu_count,
        AdmissionReasonCode.missing_gpu,
        "gpu_count",
        reasons,
        dispositions,
    )
    known_vram = [gpu.vram.available_mb for gpu in snapshot.gpus if gpu.vram.available_mb is not None]
    _strict_or_degraded(
        "VRAM availability",
        sum(known_vram) if known_vram else None,
        requirement.minimum_vram_available_mb,
        requirement.degraded_vram_available_mb,
        AdmissionReasonCode.insufficient_vram,
        "vram_available_mb",
        reasons,
        dispositions,
    )
    _strict_only(
        "disk availability",
        snapshot.disk.available_mb,
        requirement.minimum_disk_available_mb,
        AdmissionReasonCode.insufficient_disk,
        "disk_available_mb",
        reasons,
        dispositions,
    )
    services = {service.id.strip().casefold(): service.reachable for service in snapshot.services}
    for service_id in requirement.required_services:
        observed = services.get(service_id)
        if observed is True:
            continue
        unknown = service_id not in services or observed is None
        reasons.append(
            AdmissionReason(
                code=(
                    AdmissionReasonCode.service_unknown
                    if unknown
                    else AdmissionReasonCode.service_unavailable
                ),
                message=f"required service {service_id} availability is " + ("unknown" if unknown else "unavailable"),
                mandatory=True,
                observed_value=observed,
                required_value=True,
                service_id=service_id,
                metric="service_reachable",
            )
        )
        dispositions.append(_Disposition.wait if unknown else _Disposition.deny)
    return dispositions


def _strict_only(
    label: str,
    observed: float | int | None,
    strict: float | int | None,
    code: AdmissionReasonCode,
    metric: str,
    reasons: list[AdmissionReason],
    dispositions: list[_Disposition],
) -> None:
    if strict is None or observed is not None and observed >= strict:
        return
    reasons.append(
        AdmissionReason(
            code=code,
            message=f"{label} is " + ("unknown" if observed is None else "insufficient"),
            mandatory=True,
            observed_value=observed,
            required_value=strict,
            metric=metric,
        )
    )
    dispositions.append(_Disposition.wait if observed is None else _Disposition.deny)


def _strict_or_degraded(
    label: str,
    observed: float | int | None,
    strict: float | int | None,
    degraded: float | int | None,
    code: AdmissionReasonCode,
    metric: str,
    reasons: list[AdmissionReason],
    dispositions: list[_Disposition],
) -> None:
    if strict is None or observed is not None and observed >= strict:
        return
    if degraded is not None and observed is not None and observed >= degraded:
        reasons.append(
            AdmissionReason(
                code=AdmissionReasonCode.degraded_requirement_used,
                message=f"{label} uses the declared degraded requirement",
                mandatory=False,
                observed_value=observed,
                required_value=degraded,
                metric=metric,
            )
        )
        dispositions.append(_Disposition.degraded)
        return
    reasons.append(
        AdmissionReason(
            code=code,
            message=f"{label} is " + ("unknown" if observed is None else "insufficient"),
            mandatory=True,
            observed_value=observed,
            required_value=degraded if degraded is not None else strict,
            metric=metric,
        )
    )
    dispositions.append(_Disposition.wait if observed is None else _Disposition.deny)


def _aggregate(dispositions: list[_Disposition]) -> AdmissionOutcome:
    if _Disposition.deny in dispositions:
        return AdmissionOutcome.deny
    if _Disposition.wait in dispositions:
        return AdmissionOutcome.wait
    if _Disposition.degraded in dispositions:
        return AdmissionOutcome.degraded
    return AdmissionOutcome.allow


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
