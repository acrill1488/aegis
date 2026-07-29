from datetime import datetime, timedelta, timezone
import importlib
import math
import sys

import pytest
from pydantic import ValidationError

from aegis.greenboost import (
    AdmissionController,
    AdmissionDecision,
    AdmissionOutcome,
    AdmissionReason,
    AdmissionReasonCode,
    AdmissionRequest,
    PolicyEngine,
    PolicyOperator,
    PolicyOutcome,
    PolicyRule,
    PolicySeverity,
    ResourceMetric,
    ResourcePolicy,
    ResourceRequirement,
    ResourceStatistics,
)
from aegis.greenboost.contracts import (
    CPUState,
    DiskState,
    GPUState,
    MemoryState,
    NodeReference,
    NodeScope,
    ResourceSnapshot,
    ServiceResourceState,
)


NOW = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
NODE = NodeReference(id="local", scope=NodeScope.local)


def snapshot(**changes):
    values = {"timestamp": NOW, "node": NODE}
    values.update(changes)
    return ResourceSnapshot(**values)


def requirement(**changes):
    return ResourceRequirement(**changes)


def request(*, requirement_=None, policies=(), **changes):
    values = {
        "id": "execution-1",
        "created_at": NOW,
        "requirement": requirement_ or requirement(),
        "policy_evaluations": policies,
    }
    values.update(changes)
    return AdmissionRequest(**values)


def decide(requirement_=None, current=None, policies=(), **changes):
    return AdmissionController().evaluate(
        request(requirement_=requirement_, policies=policies),
        current or snapshot(),
        evaluated_at=changes.pop("evaluated_at", NOW),
        **changes,
    )


def evaluation(outcome, severity=PolicySeverity.critical, *, rule_id="rule", metric=ResourceMetric.ram_available_mb):
    rule = PolicyRule(
        id=rule_id,
        metric=metric,
        operator=PolicyOperator.greater_than_or_equal,
        threshold=100,
        severity=severity,
        description=f"{rule_id} diagnostic",
    )
    available = 200 if outcome is PolicyOutcome.passed else 50
    current = snapshot(ram=MemoryState(available_mb=available))
    if outcome is PolicyOutcome.unknown:
        current = snapshot(ram=MemoryState())
    if outcome is PolicyOutcome.not_applicable:
        rule = rule.model_copy(update={"enabled": False})
    return PolicyEngine().evaluate(ResourcePolicy(id="policy-" + rule_id, version="1", rules=(rule,)), current)


@pytest.mark.parametrize("value", [
    requirement(),
    request(),
    AdmissionReason(code="admitted", message="ok", mandatory=False),
    decide(),
])
def test_public_contracts_are_immutable(value):
    with pytest.raises(ValidationError):
        setattr(value, next(iter(type(value).model_fields)), "changed")


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (ResourceRequirement, {}),
        (AdmissionRequest, {"id": "x", "created_at": NOW}),
        (AdmissionReason, {"code": "admitted", "message": "ok", "mandatory": False}),
        (
            AdmissionDecision,
            {
                "request_id": "x", "outcome": "allow", "snapshot_timestamp": NOW,
                "node": NODE, "evaluated_at": NOW, "reasons": (),
                "policy_evaluation_count": 0, "mandatory_failure_count": 0,
                "unknown_count": 0, "degraded_requirement_used": False,
            },
        ),
    ],
)
def test_extra_fields_are_forbidden(model, values):
    with pytest.raises(ValidationError):
        model(**values, unexpected=True)


def test_request_validation_and_policy_identity():
    with pytest.raises(ValidationError):
        request(id=" ")
    with pytest.raises(ValidationError):
        request(created_at=NOW.replace(tzinfo=None))
    one = evaluation(PolicyOutcome.passed)
    with pytest.raises(ValidationError, match="duplicate"):
        request(policies=(one, one))
    assert request(created_at=NOW.astimezone(timezone(timedelta(hours=3)))).created_at == NOW
    assert isinstance(request(policies=[one]).policy_evaluations, tuple)


@pytest.mark.parametrize("value", [True, math.nan, math.inf, -math.inf, -1])
def test_invalid_numeric_requirements_are_rejected(value):
    with pytest.raises(ValidationError):
        requirement(minimum_ram_available_mb=value)
    with pytest.raises(ValidationError):
        request(maximum_snapshot_age_seconds=value)


def test_percentage_services_and_degraded_validation():
    with pytest.raises(ValidationError):
        requirement(minimum_cpu_available_percent=101)
    with pytest.raises(ValidationError, match="duplicate"):
        requirement(required_services=("OCR", "ocr"))
    with pytest.raises(ValidationError):
        requirement(degraded_ram_available_mb=1)
    with pytest.raises(ValidationError):
        requirement(minimum_ram_available_mb=10, allow_degraded=True, degraded_ram_available_mb=11)
    value = requirement(required_services=[" OCR "])
    assert value.required_services == ("ocr",)


@pytest.mark.parametrize(
    ("policy_outcome", "severity", "degraded", "expected"),
    [
        (PolicyOutcome.failed, PolicySeverity.critical, False, AdmissionOutcome.deny),
        (PolicyOutcome.unknown, PolicySeverity.critical, False, AdmissionOutcome.wait),
        (PolicyOutcome.failed, PolicySeverity.warning, False, AdmissionOutcome.allow),
        (PolicyOutcome.failed, PolicySeverity.warning, True, AdmissionOutcome.degraded),
        (PolicyOutcome.unknown, PolicySeverity.warning, True, AdmissionOutcome.allow),
        (PolicyOutcome.failed, PolicySeverity.info, True, AdmissionOutcome.allow),
        (PolicyOutcome.not_applicable, PolicySeverity.critical, False, AdmissionOutcome.allow),
    ],
)
def test_policy_severity_mapping(policy_outcome, severity, degraded, expected):
    decision = decide(
        requirement(allow_degraded=degraded),
        policies=(evaluation(policy_outcome, severity),),
    )
    assert decision.outcome is expected


def test_warning_unknown_only_degrades_a_declared_degradable_requirement():
    req = requirement(
        minimum_ram_available_mb=100,
        allow_degraded=True,
        degraded_ram_available_mb=50,
    )
    decision = decide(req, snapshot(ram=MemoryState(available_mb=100)), policies=(
        evaluation(PolicyOutcome.unknown, PolicySeverity.warning),
    ))
    assert decision.outcome is AdmissionOutcome.degraded


def test_policy_precedence_order_and_evidence_are_preserved():
    warning = evaluation(PolicyOutcome.failed, PolicySeverity.warning, rule_id="first")
    unknown = evaluation(PolicyOutcome.unknown, rule_id="second")
    failed = evaluation(PolicyOutcome.failed, rule_id="third")
    decision = decide(requirement(allow_degraded=True), policies=(warning, unknown, failed))
    assert decision.outcome is AdmissionOutcome.deny
    policy_reasons = [reason for reason in decision.reasons if reason.policy_id]
    assert [reason.rule_id for reason in policy_reasons] == ["first", "second", "third"]
    assert policy_reasons[0].observed_value == 50
    assert policy_reasons[0].required_value == 100
    assert decision.mandatory_failure_count == 1
    assert decision.unknown_count == 1


@pytest.mark.parametrize(
    ("required", "observed", "expected"),
    [(40, 60, AdmissionOutcome.allow), (40, 61, AdmissionOutcome.deny), (40, None, AdmissionOutcome.wait)],
)
def test_cpu_available_percent_is_derived(required, observed, expected):
    utilization = None if observed is None else observed
    decision = decide(
        requirement(minimum_cpu_available_percent=required),
        snapshot(cpu=CPUState(utilization_percent=utilization)),
    )
    assert decision.outcome is expected
    if observed == 60:
        assert decision.outcome is AdmissionOutcome.allow


@pytest.mark.parametrize(
    ("field", "state", "minimum", "expected"),
    [
        ("minimum_ram_available_mb", {"ram": MemoryState(available_mb=100)}, 100, AdmissionOutcome.allow),
        ("minimum_ram_available_mb", {"ram": MemoryState(available_mb=99)}, 100, AdmissionOutcome.deny),
        ("minimum_ram_available_mb", {"ram": MemoryState()}, 100, AdmissionOutcome.wait),
        ("minimum_disk_available_mb", {"disk": DiskState(available_mb=100)}, 100, AdmissionOutcome.allow),
        ("minimum_disk_available_mb", {"disk": DiskState(available_mb=99)}, 100, AdmissionOutcome.deny),
        ("minimum_disk_available_mb", {"disk": DiskState()}, 100, AdmissionOutcome.wait),
        ("minimum_gpu_count", {"gpus": (GPUState(),)}, 1, AdmissionOutcome.allow),
        ("minimum_gpu_count", {"gpus": ()}, 1, AdmissionOutcome.deny),
    ],
)
def test_direct_resource_boundaries(field, state, minimum, expected):
    assert decide(requirement(**{field: minimum}), snapshot(**state)).outcome is expected


def test_vram_uses_sum_of_known_node_values_and_unknown_waits():
    mixed = snapshot(gpus=(
        GPUState(vram=MemoryState(available_mb=100)),
        GPUState(vram=MemoryState()),
        GPUState(vram=MemoryState(available_mb=200)),
    ))
    assert decide(requirement(minimum_vram_available_mb=300), mixed).outcome is AdmissionOutcome.allow
    assert decide(requirement(minimum_vram_available_mb=301), mixed).outcome is AdmissionOutcome.deny
    unknown = snapshot(gpus=(GPUState(vram=MemoryState()),))
    assert decide(requirement(minimum_vram_available_mb=1), unknown).outcome is AdmissionOutcome.wait


def test_degraded_resource_requirements_and_precedence():
    req = requirement(
        minimum_ram_available_mb=100,
        minimum_vram_available_mb=100,
        minimum_gpu_count=2,
        allow_degraded=True,
        degraded_ram_available_mb=50,
        degraded_vram_available_mb=50,
        degraded_gpu_count=1,
    )
    current = snapshot(
        ram=MemoryState(available_mb=60),
        gpus=(GPUState(vram=MemoryState(available_mb=60)),),
    )
    decision = decide(req, current)
    assert decision.outcome is AdmissionOutcome.degraded
    assert decision.degraded_requirement_used
    degraded_reasons = [
        reason for reason in decision.reasons
        if reason.code is AdmissionReasonCode.degraded_requirement_used
    ]
    assert [reason.metric for reason in degraded_reasons] == [
        "ram_available_mb", "gpu_count", "vram_available_mb"
    ]
    assert decide(req, snapshot(ram=MemoryState(available_mb=49), gpus=current.gpus)).outcome is AdmissionOutcome.deny
    assert decide(req, snapshot(ram=MemoryState(), gpus=current.gpus)).outcome is AdmissionOutcome.wait
    critical = evaluation(PolicyOutcome.failed)
    assert decide(req, current, policies=(critical,)).outcome is AdmissionOutcome.deny


def test_strict_pass_ignores_degraded_requirement():
    req = requirement(minimum_ram_available_mb=100, allow_degraded=True, degraded_ram_available_mb=50)
    decision = decide(req, snapshot(ram=MemoryState(available_mb=100)))
    assert decision.outcome is AdmissionOutcome.allow
    assert not decision.degraded_requirement_used


def test_service_reachability_and_order():
    services = (
        ServiceResourceState(id="ollama", state="up", reachable=False),
        ServiceResourceState(id="remote-runtime:ubuntu", state="unknown", reachable=None),
        ServiceResourceState(id="ocr", state="up", reachable=True),
    )
    req = requirement(required_services=("ocr", "ollama", "remote-runtime:ubuntu", "missing"))
    decision = decide(req, snapshot(services=services))
    assert decision.outcome is AdmissionOutcome.deny
    service_reasons = [reason for reason in decision.reasons if reason.service_id]
    assert [reason.service_id for reason in service_reasons] == [
        "ollama", "remote-runtime:ubuntu", "missing"
    ]
    assert [reason.code for reason in service_reasons] == [
        AdmissionReasonCode.service_unavailable,
        AdmissionReasonCode.service_unknown,
        AdmissionReasonCode.service_unknown,
    ]


def test_snapshot_freshness_boundaries_and_future_handling():
    req = request(maximum_snapshot_age_seconds=10)
    controller = AdmissionController()
    assert controller.evaluate(req, snapshot(), evaluated_at=NOW + timedelta(seconds=10)).outcome is AdmissionOutcome.allow
    assert controller.evaluate(req, snapshot(), evaluated_at=NOW + timedelta(seconds=10.001)).outcome is AdmissionOutcome.wait
    assert controller.evaluate(req, snapshot(), evaluated_at=NOW - timedelta(microseconds=1)).outcome is AdmissionOutcome.wait
    with pytest.raises(ValueError):
        controller.evaluate(req, snapshot(), evaluated_at=NOW.replace(tzinfo=None))
    old = snapshot(timestamp=NOW - timedelta(days=10))
    assert decide(current=old, evaluated_at=NOW).outcome is AdmissionOutcome.allow


def test_no_policy_behavior_and_admitted_reason():
    empty = decide()
    assert empty.outcome is AdmissionOutcome.allow
    assert empty.reasons[0].code is AdmissionReasonCode.no_applicable_policy
    applicable = decide(policies=(evaluation(PolicyOutcome.passed),))
    assert [reason.code for reason in applicable.reasons] == [AdmissionReasonCode.admitted]
    denied = decide(requirement(minimum_ram_available_mb=1), snapshot(ram=MemoryState()))
    assert denied.outcome is AdmissionOutcome.wait


def test_statistics_are_accepted_but_do_not_change_decision():
    controller = AdmissionController()
    req = request(policies=(evaluation(PolicyOutcome.passed),))
    current = snapshot()
    baseline = controller.evaluate(req, current, evaluated_at=NOW)
    with_stats = controller.evaluate(
        req, current, ResourceStatistics(snapshot_count=100, peak_cpu_load=100), evaluated_at=NOW
    )
    assert with_stats == baseline


def test_decision_identity_purity_serialization_and_statelessness():
    controller = AdmissionController()
    req = request(policies=(evaluation(PolicyOutcome.passed),))
    current = snapshot()
    before_request = req.model_dump_json()
    before_snapshot = current.model_dump_json()
    first = controller.evaluate(req, current, evaluated_at=NOW)
    second = controller.evaluate(req, current, evaluated_at=NOW)
    assert first == second
    assert first.request_id == req.id
    assert first.node == NODE
    assert first.snapshot_timestamp == NOW
    assert first.evaluated_at == NOW
    assert req.model_dump_json() == before_request
    assert current.model_dump_json() == before_snapshot
    assert controller.__slots__ == ()
    assert AdmissionDecision.model_validate_json(first.model_dump_json()) == first


def test_module_import_has_no_io_or_background_side_effects(monkeypatch):
    import builtins
    import threading
    import urllib.request

    calls = []
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: calls.append("file"))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: calls.append("network"))
    before = set(threading.enumerate())
    sys.modules.pop("aegis.greenboost.admission", None)
    importlib.import_module("aegis.greenboost.admission")
    assert calls == []
    assert set(threading.enumerate()) == before
