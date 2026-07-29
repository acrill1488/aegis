from datetime import datetime, timezone
import importlib
import math
import sys

import pytest
from pydantic import ValidationError

from aegis.greenboost import (
    PolicyEngine,
    PolicyEvaluation,
    PolicyOperator,
    PolicyOutcome,
    PolicyRule,
    PolicyRuleResult,
    PolicySeverity,
    ResourceMetric,
    ResourcePolicy,
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


def rule(**changes):
    values = {
        "id": "cpu-limit",
        "metric": ResourceMetric.cpu_utilization_percent,
        "operator": PolicyOperator.less_than,
        "threshold": 80,
        "severity": PolicySeverity.warning,
        "description": "CPU must retain headroom",
    }
    values.update(changes)
    return PolicyRule(**values)


def policy(*rules, **changes):
    values = {"id": "resource-policy", "version": "1", "rules": rules}
    values.update(changes)
    return ResourcePolicy(**values)


def snapshot(**changes):
    values = {"timestamp": NOW, "node": NODE}
    values.update(changes)
    return ResourceSnapshot(**values)


def evaluate(one_rule, value=None):
    current = value or snapshot(cpu=CPUState(utilization_percent=50))
    return PolicyEngine().evaluate(policy(one_rule), current).results[0]


@pytest.mark.parametrize("contract", [rule(), policy(rule())])
def test_configuration_contracts_are_immutable(contract):
    with pytest.raises(ValidationError):
        contract.id = "changed"


def test_result_contracts_are_immutable():
    result = evaluate(rule())
    evaluation = PolicyEngine().evaluate(policy(rule()), snapshot(cpu=CPUState(utilization_percent=50)))
    with pytest.raises(ValidationError):
        result.outcome = PolicyOutcome.failed
    with pytest.raises(ValidationError):
        evaluation.pass_count = 0
    assert isinstance(result, PolicyRuleResult)
    assert isinstance(evaluation, PolicyEvaluation)


@pytest.mark.parametrize("model,values", [
    (PolicyRule, {"id": "x", "metric": "gpu_count", "operator": "equal", "threshold": 1}),
    (ResourcePolicy, {"id": "x", "version": "1"}),
])
def test_extra_fields_are_forbidden(model, values):
    with pytest.raises(ValidationError):
        model(**values, unexpected=True)


@pytest.mark.parametrize("field", ["id", "version"])
def test_empty_policy_identity_is_rejected(field):
    with pytest.raises(ValidationError):
        policy(**{field: " "})


def test_empty_rule_id_and_duplicate_ids_are_rejected():
    with pytest.raises(ValidationError):
        rule(id=" ")
    with pytest.raises(ValidationError, match="duplicate"):
        policy(rule(), rule())


@pytest.mark.parametrize("threshold", [None, math.nan, math.inf, -math.inf, True])
def test_numeric_threshold_must_be_finite_non_boolean(threshold):
    with pytest.raises(ValidationError):
        rule(threshold=threshold)


@pytest.mark.parametrize("operator", [PolicyOperator.is_true, PolicyOperator.is_false])
def test_boolean_operator_rejects_threshold_and_numeric_metric(operator):
    with pytest.raises(ValidationError):
        rule(operator=operator, threshold=None)
    with pytest.raises(ValidationError):
        rule(metric=ResourceMetric.docker_available, operator=operator, threshold=1)


def test_numeric_operator_rejects_boolean_metric():
    with pytest.raises(ValidationError):
        rule(metric=ResourceMetric.docker_available)


def test_rules_preserve_declared_order_and_nested_input_is_immutable():
    raw = [rule(id="first"), rule(id="second")]
    value = policy(*raw)
    raw.reverse()
    assert tuple(item.id for item in value.rules) == ("first", "second")
    assert isinstance(value.rules, tuple)


@pytest.mark.parametrize(("operator", "observed", "threshold", "outcome"), [
    (PolicyOperator.less_than, 4, 5, PolicyOutcome.passed),
    (PolicyOperator.less_than, 5, 5, PolicyOutcome.failed),
    (PolicyOperator.less_than_or_equal, 5, 5, PolicyOutcome.passed),
    (PolicyOperator.greater_than, 6, 5, PolicyOutcome.passed),
    (PolicyOperator.greater_than, 5, 5, PolicyOutcome.failed),
    (PolicyOperator.greater_than_or_equal, 5, 5, PolicyOutcome.passed),
    (PolicyOperator.equal, 5, 5, PolicyOutcome.passed),
    (PolicyOperator.not_equal, 4, 5, PolicyOutcome.passed),
])
def test_numeric_operators(operator, observed, threshold, outcome):
    result = evaluate(
        rule(metric=ResourceMetric.ram_used_mb, operator=operator, threshold=threshold),
        snapshot(ram=MemoryState(used_mb=observed)),
    )
    assert result.outcome is outcome


@pytest.mark.parametrize(("operator", "reachable", "outcome"), [
    (PolicyOperator.is_true, True, PolicyOutcome.passed),
    (PolicyOperator.is_true, False, PolicyOutcome.failed),
    (PolicyOperator.is_false, False, PolicyOutcome.passed),
    (PolicyOperator.is_false, True, PolicyOutcome.failed),
])
def test_boolean_operators(operator, reachable, outcome):
    result = evaluate(
        rule(id="docker", metric=ResourceMetric.docker_available, operator=operator, threshold=None),
        snapshot(services=(ServiceResourceState(id="docker", state="test", reachable=reachable),)),
    )
    assert result.outcome is outcome
    assert result.expected_value is (operator is PolicyOperator.is_true)


def test_unknown_metrics_are_neither_zero_nor_false():
    numeric = evaluate(rule(metric=ResourceMetric.ram_used_mb), snapshot())
    boolean = evaluate(
        rule(metric=ResourceMetric.docker_available, operator=PolicyOperator.is_true, threshold=None),
        snapshot(),
    )
    assert (numeric.outcome, numeric.observed_value) == (PolicyOutcome.unknown, None)
    assert (boolean.outcome, boolean.observed_value) == (PolicyOutcome.unknown, None)


def test_disabled_rule_and_policy_are_not_applicable_without_extraction():
    disabled_rule = evaluate(rule(enabled=False), snapshot(cpu=CPUState(utilization_percent=99)))
    disabled_policy = PolicyEngine().evaluate(
        policy(rule(), enabled=False), snapshot(cpu=CPUState(utilization_percent=99))
    )
    assert disabled_rule.outcome is PolicyOutcome.not_applicable
    assert disabled_rule.reason_code == "rule_disabled"
    assert disabled_policy.overall_outcome is PolicyOutcome.not_applicable
    assert disabled_policy.results[0].reason_code == "policy_disabled"
    assert disabled_policy.results[0].observed_value is None


@pytest.mark.parametrize("gpus", [(), (GPUState(),), (GPUState(), GPUState())])
def test_missing_or_absent_vram_is_unknown(gpus):
    result = evaluate(rule(metric=ResourceMetric.vram_used_mb), snapshot(gpus=gpus))
    assert result.outcome is PolicyOutcome.unknown


def test_node_level_vram_sums_known_values_and_gpu_count():
    current = snapshot(gpus=(
        GPUState(vram=MemoryState(used_mb=100, available_mb=None)),
        GPUState(vram=MemoryState(used_mb=None, available_mb=700)),
        GPUState(vram=MemoryState(used_mb=300, available_mb=200)),
    ))
    engine = PolicyEngine()
    results = engine.evaluate(policy(
        rule(id="used", metric=ResourceMetric.vram_used_mb, operator="equal", threshold=400),
        rule(id="available", metric=ResourceMetric.vram_available_mb, operator="equal", threshold=900),
        rule(id="count", metric=ResourceMetric.gpu_count, operator="equal", threshold=3),
    ), current).results
    assert [item.observed_value for item in results] == [400, 900, 3]
    assert all(item.outcome is PolicyOutcome.passed for item in results)
    assert len(results) == 3


def test_vram_utilization_requires_used_and_available_totals():
    complete = snapshot(gpus=(
        GPUState(vram=MemoryState(used_mb=100, available_mb=300)),
        GPUState(vram=MemoryState(used_mb=300, available_mb=300)),
    ))
    result = evaluate(
        rule(metric=ResourceMetric.vram_utilization_percent, operator="equal", threshold=40),
        complete,
    )
    assert result.observed_value == 40
    assert result.outcome is PolicyOutcome.passed
    incomplete = snapshot(gpus=(GPUState(vram=MemoryState(used_mb=100)),))
    assert evaluate(rule(metric=ResourceMetric.vram_utilization_percent), incomplete).outcome is PolicyOutcome.unknown


def test_ram_and_disk_utilization_use_canonical_totals():
    current = snapshot(
        ram=MemoryState(total_mb=1000, used_mb=250),
        disk=DiskState(total_mb=2000, used_mb=500),
    )
    results = PolicyEngine().evaluate(policy(
        rule(id="ram", metric=ResourceMetric.ram_utilization_percent, operator="equal", threshold=25),
        rule(id="disk", metric=ResourceMetric.disk_utilization_percent, operator="equal", threshold=25),
    ), current).results
    assert [item.observed_value for item in results] == [25, 25]


def test_counts_order_evidence_and_overall_precedence():
    rules = (
        rule(id="pass", threshold=60),
        rule(id="unknown", metric=ResourceMetric.ram_used_mb),
        rule(id="fail", operator=PolicyOperator.greater_than, threshold=60),
        rule(id="disabled", enabled=False),
    )
    value = PolicyEngine().evaluate(policy(*rules), snapshot(cpu=CPUState(utilization_percent=50)))
    assert [item.rule_id for item in value.results] == [item.id for item in rules]
    assert (value.total_rule_count, value.pass_count, value.fail_count) == (4, 1, 1)
    assert (value.unknown_count, value.not_applicable_count) == (1, 1)
    assert value.overall_outcome is PolicyOutcome.failed
    assert value.results[0].observed_value == 50
    assert value.results[0].expected_value == 60
    assert value.snapshot_timestamp == NOW
    assert value.node == NODE


@pytest.mark.parametrize(("rules", "overall"), [
    ((rule(id="unknown", metric=ResourceMetric.ram_used_mb),), PolicyOutcome.unknown),
    ((rule(id="pass", threshold=60),), PolicyOutcome.passed),
    ((rule(id="disabled", enabled=False),), PolicyOutcome.not_applicable),
    ((), PolicyOutcome.not_applicable),
])
def test_overall_outcome_precedence(rules, overall):
    value = PolicyEngine().evaluate(policy(*rules), snapshot(cpu=CPUState(utilization_percent=50)))
    assert value.overall_outcome is overall


@pytest.mark.parametrize(("metric", "service_id"), [
    (ResourceMetric.docker_available, "docker"),
    (ResourceMetric.ollama_available, "ollama"),
    (ResourceMetric.ocr_available, "unlimited-ocr"),
    (ResourceMetric.comfyui_available, "comfyui"),
    (ResourceMetric.embedding_available, "bge-m3"),
    (ResourceMetric.remote_available, "remote-runtime:ubuntu-ai"),
])
def test_service_health_true_false_and_missing(metric, service_id):
    required = rule(id=service_id, metric=metric, operator="is_true", threshold=None)
    assert evaluate(required, snapshot(services=(ServiceResourceState(id=service_id, state="ok", reachable=True),))).outcome is PolicyOutcome.passed
    assert evaluate(required, snapshot(services=(ServiceResourceState(id=service_id, state="down", reachable=False),))).outcome is PolicyOutcome.failed
    assert evaluate(required, snapshot()).outcome is PolicyOutcome.unknown


def test_evaluation_is_pure_repeatable_and_engine_has_no_state():
    current = snapshot(cpu=CPUState(utilization_percent=50))
    configured = policy(rule())
    before_snapshot = current.model_dump_json()
    before_policy = configured.model_dump_json()
    engine = PolicyEngine()
    first = engine.evaluate(configured, current)
    second = engine.evaluate(configured, current)
    assert first == second
    assert current.model_dump_json() == before_snapshot
    assert configured.model_dump_json() == before_policy
    assert not hasattr(engine, "__dict__")


def test_evaluate_many_preserves_policy_order():
    evaluations = PolicyEngine().evaluate_many(
        (policy(rule(), id="first"), policy(rule(), id="second")),
        snapshot(cpu=CPUState(utilization_percent=50)),
    )
    assert tuple(item.policy_id for item in evaluations) == ("first", "second")


def test_policy_module_import_has_no_io_dependencies():
    sys.modules.pop("aegis.greenboost.policy", None)
    before = set(sys.modules)
    importlib.import_module("aegis.greenboost.policy")
    loaded = set(sys.modules) - before
    assert not {"httpx", "yaml", "socket", "threading"}.intersection(loaded)
