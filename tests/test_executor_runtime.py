from aegis.capabilities import (
    CapabilityDescriptor,
    CapabilityInvocationRequest,
    CapabilityInvocationResult,
    CapabilityRuntime,
)
from aegis.executor import ExecutionPlan, ExecutionStep, ExecutorRuntime


class FakeCapabilityRuntime:
    def __init__(self):
        self.invocations = []
        self.results = []

    def invoke(self, request):
        self.invocations.append(request)
        if self.results:
            return self.results.pop(0)
        return CapabilityInvocationResult(
            success=True,
            capability_id=request.capability_id,
            output={"text": "done"},
        )


def test_executor_runtime_runs_observe_action_observe_validate_loop():
    capability_runtime = FakeCapabilityRuntime()
    runtime = ExecutorRuntime(capability_runtime=capability_runtime)
    plan = ExecutionPlan(
        goal="demo",
        steps=[
            ExecutionStep(
                id="step_1",
                description="Open page",
                observe=lambda step: {"text": "ready"},
                action={"capability_id": "demo.action", "payload": {"value": 1}},
                validate={"type": "contains_text", "text": "ready"},
            )
        ],
    )

    result = runtime.execute(plan)

    assert result.success is True
    assert result.completed_steps == ["step_1"]
    assert [item["event"] for item in result.history] == [
        "before",
        "reason",
        "action",
        "after",
        "validate",
        "step.completed",
    ]
    assert capability_runtime.invocations[0].capability_id == "demo.action"
    assert capability_runtime.invocations[0].caller == "executor.runtime"


def test_executor_runtime_retries_until_validation_passes():
    observations = iter(
        [
            {"text": "before"},
            {"text": "missing"},
            {"text": "before"},
            {"text": "expected"},
        ]
    )
    capability_runtime = FakeCapabilityRuntime()
    runtime = ExecutorRuntime(capability_runtime=capability_runtime)
    plan = ExecutionPlan(
        goal="retry",
        steps=[
            ExecutionStep(
                id="step_retry",
                observe=lambda step: next(observations),
                action={"capability_id": "demo.action"},
                validate={"type": "contains_text", "text": "expected"},
                retry_limit=1,
            )
        ],
    )

    result = runtime.execute(plan)

    assert result.success is True
    assert len(capability_runtime.invocations) == 2
    assert "retry" in [item["event"] for item in result.history]


class Registry:
    def __init__(self):
        self.items = {}

    def register(self, name, value):
        self.items[name] = value

    def get(self, name):
        return self.items.get(name)


class Core:
    events = None

    def __init__(self):
        self.registry = Registry()


def test_executor_execute_capability_invokes_runtime_provider():
    core = Core()
    capability_runtime = CapabilityRuntime(core)
    executor_runtime = ExecutorRuntime(capability_runtime=capability_runtime, core=core)
    core.registry.register("executor_runtime", executor_runtime)
    capability_runtime.register(
        CapabilityDescriptor(
            id="executor.execute",
            name="Execute Agent Executor Plan",
        ),
        {
            "type": "runtime",
            "runtime": "executor_runtime",
            "method": "execute_payload",
        },
    )

    result = capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="executor.execute",
            payload={
                "goal": "capability",
                "steps": [
                    {
                        "id": "noop",
                        "description": "No-op",
                        "validate": {"type": "custom", "callable": lambda *args: True},
                    }
                ],
            },
        )
    )

    assert result.success is True
    assert result.output["success"] is True
    assert result.output["completed_steps"] == ["noop"]
