from aegis.planning import ExecutionGraph, TaskPlanningRuntime


def test_create_task_and_empty_plan_persist(tmp_path):
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
    assert plan.graph == ExecutionGraph()

    reloaded = TaskPlanningRuntime(tmp_path)

    assert reloaded.get_task("task_test") == task
    reloaded_plan = reloaded.get_plan("plan_test")
    assert reloaded_plan is not None
    assert reloaded_plan.id == plan.id
    assert reloaded_plan.task_id == task.id
    assert reloaded_plan.status == "created"
    assert reloaded_plan.graph == ExecutionGraph()


def test_create_plan_requires_existing_task(tmp_path):
    runtime = TaskPlanningRuntime(tmp_path)

    try:
        runtime.create_plan("missing")
    except KeyError as exc:
        assert exc.args[0] == "Task not found: missing"
    else:
        raise AssertionError("create_plan accepted a missing task")
