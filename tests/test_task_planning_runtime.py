from aegis.planning import TaskPlanningRuntime
from aegis.planning.models import ExecutionGraph, Plan, PlanStep


class FakeCapabilityRuntime:
    def __init__(self, existing):
        self.existing = set(existing)
        self.invocations = []
        self.results = {}
        self.core = None

    def resolve(self, capability_id):
        if capability_id in self.existing:
            return {"capability_id": capability_id}
        return None

    def invoke(self, request):
        from aegis.capabilities import CapabilityInvocationResult

        self.invocations.append(request)
        result = self.results.get(request.capability_id)
        if result is not None:
            return result
        return CapabilityInvocationResult(
            success=True,
            capability_id=request.capability_id,
            output={"capability_id": request.capability_id},
        )


class FakeEventBus:
    def __init__(self):
        self.events = []

    def publish(self, event_type, source, payload=None, trace_id=None):
        self.events.append(
            {
                "type": event_type,
                "source": source,
                "payload": payload or {},
                "trace_id": trace_id,
            }
        )


class FakeCore:
    def __init__(self, events):
        self.events = events


def test_create_task_and_default_plan_persist(tmp_path):
    runtime = TaskPlanningRuntime(tmp_path)

    task = runtime.create_task(
        goal="Prepare a brief",
        priority=70,
        constraints={"max_duration_ms": 120000},
        metadata={"caller": "test"},
        task_id="task_test",
    )
    plan = runtime.create_plan(task.id, plan_id="plan_test")

    assert task.id == "task_test"
    assert plan.id == "plan_test"
    assert plan.task_id == task.id
    assert plan.status == "created"
    assert [step.id for step in plan.graph.nodes] == ["step_echo"]
    assert plan.graph.nodes[0].capability_id == "echo"
    assert plan.graph.nodes[0].inputs == {"message": "Prepare a brief"}
    assert plan.graph.edges == []

    reloaded = TaskPlanningRuntime(tmp_path)

    assert reloaded.get_task("task_test") == task
    reloaded_plan = reloaded.get_plan("plan_test")
    assert reloaded_plan is not None
    assert reloaded_plan.id == plan.id
    assert reloaded_plan.task_id == task.id
    assert reloaded_plan.status == "created"
    assert reloaded_plan.graph == plan.graph


def test_create_plan_requires_existing_task(tmp_path):
    runtime = TaskPlanningRuntime(tmp_path)

    try:
        runtime.create_plan("missing")
    except KeyError as exc:
        assert exc.args[0] == "Task not found: missing"
    else:
        raise AssertionError("create_plan accepted a missing task")


def test_create_plan_builds_presentation_graph(tmp_path):
    runtime = TaskPlanningRuntime(
        tmp_path,
        capability_runtime=FakeCapabilityRuntime(
            {"windows.context.snapshot", "windows.system.status", "echo"}
        ),
    )
    task = runtime.create_task("Create a presentation about AEGIS")

    plan = runtime.create_plan(task.id)

    assert [step.id for step in plan.graph.nodes] == [
        "step_context",
        "step_system",
        "step_outline",
    ]
    assert [step.capability_id for step in plan.graph.nodes] == [
        "windows.context.snapshot",
        "windows.system.status",
        "echo",
    ]
    assert plan.graph.nodes[2].dependencies == ["step_context", "step_system"]
    assert plan.graph.nodes[2].inputs == {
        "message": "Create presentation outline placeholder",
    }
    assert plan.graph.edges == [
        ["step_context", "step_outline"],
        ["step_system", "step_outline"],
    ]


def test_create_plan_builds_research_graph_and_marks_missing_capability(tmp_path):
    runtime = TaskPlanningRuntime(
        tmp_path,
        capability_runtime=FakeCapabilityRuntime({"echo"}),
    )
    task = runtime.create_task(
        "\u041d\u0443\u0436\u043d\u043e "
        "\u0438\u0441\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u043d\u0438\u0435 "
        "\u0440\u044b\u043d\u043a\u0430"
    )

    plan = runtime.create_plan(task.id)

    assert [step.id for step in plan.graph.nodes] == [
        "step_context",
        "step_research_placeholder",
    ]
    assert plan.graph.edges == [["step_context", "step_research_placeholder"]]
    assert plan.graph.nodes[0].metadata == {"missing_capability": True}
    assert plan.graph.nodes[1].metadata == {}


def test_execute_plan_runs_ready_steps_in_dependency_order(tmp_path):
    event_bus = FakeEventBus()
    capability_runtime = FakeCapabilityRuntime({"echo"})
    capability_runtime.core = FakeCore(event_bus)
    runtime = TaskPlanningRuntime(tmp_path, capability_runtime=capability_runtime)
    task = runtime.create_task("Prepare a brief", task_id="task_execute")
    plan = runtime.create_plan(task.id, plan_id="plan_execute")

    execution = runtime.execute_plan(plan.id)

    assert execution.status == "completed"
    assert runtime.get_plan(plan.id).status == "completed"
    assert [request.capability_id for request in capability_runtime.invocations] == ["echo"]
    assert capability_runtime.invocations[0].caller == "planning.executor"
    assert execution.step_states["step_echo"].status == "completed"
    assert execution.step_states["step_echo"].input_snapshot == {
        "message": "Prepare a brief"
    }
    assert [event["type"] for event in event_bus.events] == [
        "planning.started",
        "planning.step.started",
        "planning.step.completed",
        "planning.completed",
    ]

    reloaded = TaskPlanningRuntime(tmp_path, capability_runtime=capability_runtime)
    reloaded_execution = reloaded.get_plan_execution(plan.id)
    assert reloaded_execution is not None
    assert reloaded_execution.status == "completed"
    assert reloaded_execution.step_states["step_echo"].status == "completed"


def test_execute_plan_stops_on_failed_step(tmp_path):
    from aegis.capabilities import CapabilityInvocationResult

    capability_runtime = FakeCapabilityRuntime({"ok", "fail", "blocked"})
    capability_runtime.results["fail"] = CapabilityInvocationResult(
        success=False,
        capability_id="fail",
        error="boom",
    )
    runtime = TaskPlanningRuntime(tmp_path, capability_runtime=capability_runtime)
    task = runtime.create_task("manual", task_id="task_failed")
    plan = Plan(
        id="plan_failed",
        task_id=task.id,
        graph=ExecutionGraph(
            nodes=[
                PlanStep(id="step_ok", capability_id="ok"),
                PlanStep(
                    id="step_fail",
                    capability_id="fail",
                    dependencies=["step_ok"],
                ),
                PlanStep(
                    id="step_blocked",
                    capability_id="blocked",
                    dependencies=["step_fail"],
                ),
            ],
        ),
    )
    runtime._plans[plan.id] = plan
    runtime._save_plans()

    execution = runtime.execute_plan(plan.id)

    assert execution.status == "failed"
    assert runtime.get_plan(plan.id).status == "failed"
    assert [request.capability_id for request in capability_runtime.invocations] == [
        "ok",
        "fail",
    ]
    assert execution.step_states["step_ok"].status == "completed"
    assert execution.step_states["step_fail"].status == "failed"
    assert "step_blocked" not in execution.step_states
