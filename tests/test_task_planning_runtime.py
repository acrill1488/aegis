from aegis.planning import TaskPlanningRuntime


class FakeCapabilityRuntime:
    def __init__(self, existing):
        self.existing = set(existing)

    def resolve(self, capability_id):
        if capability_id in self.existing:
            return {"capability_id": capability_id}
        return None


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
