from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegis.serialization import to_plain

from .executor import PlanExecutor
from .models import (
    ExecutionGraph,
    Plan,
    PlanExecution,
    PlanStep,
    StepExecutionState,
    Task,
)
from .plan_builder import PlanBuilder


DEFAULT_PLANNING_PATH = Path(r"F:\AI_WORKSPACE\planning")


class TaskPlanningRuntime:
    """Persistent Task Planning Runtime.

    The runtime stores Tasks and Plans, delegates graph construction to
    PlanBuilder, and does not execute plan steps or invoke capabilities.
    """

    def __init__(
        self,
        path: str | Path = DEFAULT_PLANNING_PATH,
        capability_runtime: Any | None = None,
        plan_builder: PlanBuilder | None = None,
    ):
        self.path = Path(path)
        self.tasks_path = self.path / "tasks.json"
        self.plans_path = self.path / "plans.json"
        self.executions_path = self.path / "executions.json"
        self.capability_runtime = capability_runtime
        self.plan_builder = plan_builder or PlanBuilder()
        self._tasks: dict[str, Task] = {}
        self._plans: dict[str, Plan] = {}
        self._executions: dict[str, PlanExecution] = {}
        self._persistence_available = True
        self._ensure_files()
        self._load()

    def create_task(
        self,
        goal: str,
        priority: int = 50,
        constraints: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> Task:
        task = Task(
            id=task_id or self._new_id("task"),
            goal=goal,
            priority=priority,
            constraints=dict(constraints or {}),
            metadata=dict(metadata or {}),
        )
        self._tasks[task.id] = task
        self._save_tasks()
        return task

    def create_plan(
        self,
        task_id: str,
        metadata: dict[str, Any] | None = None,
        plan_id: str | None = None,
        capability_runtime: Any | None = None,
    ) -> Plan:
        if task_id not in self._tasks:
            raise KeyError(f"Task not found: {task_id}")

        task = self._tasks[task_id]
        graph = self.plan_builder.build(
            task,
            capability_runtime=(
                capability_runtime
                if capability_runtime is not None
                else self.capability_runtime
            ),
        )
        plan = Plan(
            id=plan_id or self._new_id("plan"),
            task_id=task_id,
            graph=graph,
            metadata=dict(metadata or {}),
        )
        self._plans[plan.id] = plan
        self._save_plans()
        return plan

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def get_plan(self, plan_id: str) -> Plan | None:
        return self._plans.get(plan_id)

    def execute_plan(self, plan_id: str) -> PlanExecution:
        if self.capability_runtime is None:
            raise RuntimeError("TaskPlanningRuntime requires CapabilityRuntime to execute plans.")

        executor = PlanExecutor(
            capability_runtime=self.capability_runtime,
            plans=self._plans,
            event_bus=self._event_bus(),
            save_plan=self._store_plan,
            save_execution=self._store_execution,
        )
        return executor.execute(plan_id)

    def get_plan_execution(self, plan_id: str) -> PlanExecution | None:
        executions = [
            execution
            for execution in self._executions.values()
            if execution.plan_id == plan_id
        ]
        if not executions:
            return None
        return sorted(
            executions,
            key=lambda execution: (
                execution.started_at is not None,
                execution.started_at.isoformat() if execution.started_at else "",
            ),
        )[-1]

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def list_plans(self) -> list[Plan]:
        return list(self._plans.values())

    def list_executions(self) -> list[PlanExecution]:
        return list(self._executions.values())

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok" if self._persistence_available else "degraded",
            "persistence_available": self._persistence_available,
            "path": str(self.path),
            "tasks": len(self._tasks),
            "plans": len(self._plans),
            "executions": len(self._executions),
        }

    def _ensure_files(self) -> None:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            for file_path in (
                self.tasks_path,
                self.plans_path,
                self.executions_path,
            ):
                if not file_path.exists():
                    file_path.write_text("[]", encoding="utf-8")
        except OSError:
            self._persistence_available = False

    def _load(self) -> None:
        if not self._persistence_available:
            return
        self._tasks = {
            task.id: task
            for task in self._load_records(self.tasks_path, self._task_from_plain)
        }
        self._plans = {
            plan.id: plan
            for plan in self._load_records(self.plans_path, self._plan_from_plain)
        }
        self._executions = {
            execution.execution_id: execution
            for execution in self._load_records(
                self.executions_path,
                self._execution_from_plain,
            )
        }
        self._save_tasks()
        self._save_plans()
        self._save_executions()

    def _load_records(self, path: Path, factory):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []

        if isinstance(data, dict):
            items = data.values()
        elif isinstance(data, list):
            items = data
        else:
            items = []

        records = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                records.append(factory(item))
            except (KeyError, TypeError, ValueError):
                continue
        return records

    def _save_tasks(self) -> None:
        self._save(self.tasks_path, self.list_tasks())

    def _save_plans(self) -> None:
        self._save(self.plans_path, self.list_plans())

    def _save_executions(self) -> None:
        self._save(self.executions_path, self.list_executions())

    def _store_plan(self, plan: Plan) -> None:
        self._plans[plan.id] = plan
        self._save_plans()

    def _store_execution(self, execution: PlanExecution) -> None:
        self._executions[execution.execution_id] = execution
        self._save_executions()

    def _save(self, path: Path, records: list[Any]) -> None:
        if not self._persistence_available:
            return
        try:
            path.write_text(
                json.dumps(to_plain(records), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            self._persistence_available = False

    def _task_from_plain(self, item: dict[str, Any]) -> Task:
        return Task(
            id=str(item["id"]),
            goal=str(item["goal"]),
            priority=int(item.get("priority", 50)),
            constraints=self._dict(item.get("constraints")),
            metadata=self._dict(item.get("metadata")),
        )

    def _plan_from_plain(self, item: dict[str, Any]) -> Plan:
        return Plan(
            id=str(item["id"]),
            task_id=str(item["task_id"]),
            status=str(item.get("status", "created")),
            graph=self._graph_from_plain(item.get("graph")),
            created_at=self._datetime(item.get("created_at")),
            metadata=self._dict(item.get("metadata")),
        )

    def _graph_from_plain(self, value: Any) -> ExecutionGraph:
        if not isinstance(value, dict):
            return ExecutionGraph()

        nodes = value.get("nodes") or []
        if not isinstance(nodes, list):
            nodes = []

        edges = value.get("edges") or []
        if not isinstance(edges, list):
            edges = []

        return ExecutionGraph(
            nodes=[
                self._step_from_plain(node)
                for node in nodes
                if isinstance(node, dict)
            ],
            edges=[
                [str(part) for part in edge]
                for edge in edges
                if isinstance(edge, list)
            ],
            metadata=self._dict(value.get("metadata")),
        )

    def _step_from_plain(self, item: dict[str, Any]) -> PlanStep:
        dependencies = item.get("dependencies") or []
        if not isinstance(dependencies, list):
            dependencies = []

        return PlanStep(
            id=str(item["id"]),
            capability_id=str(item["capability_id"]),
            inputs=self._dict(item.get("inputs")),
            outputs=self._dict(item.get("outputs")),
            dependencies=[str(dependency) for dependency in dependencies],
            retry_policy=self._dict(item.get("retry_policy")),
            timeout=self._dict(item.get("timeout")),
            metadata=self._dict(item.get("metadata")),
        )

    def _execution_from_plain(self, item: dict[str, Any]) -> PlanExecution:
        step_states = item.get("step_states") or {}
        if not isinstance(step_states, dict):
            step_states = {}

        return PlanExecution(
            execution_id=str(item["execution_id"]),
            plan_id=str(item["plan_id"]),
            task_id=str(item["task_id"]),
            status=str(item.get("status", "created")),
            started_at=self._optional_datetime(item.get("started_at")),
            completed_at=self._optional_datetime(item.get("completed_at")),
            step_states={
                str(step_id): self._step_state_from_plain(state)
                for step_id, state in step_states.items()
                if isinstance(state, dict)
            },
            trace_id=item.get("trace_id"),
            warnings=[
                str(warning)
                for warning in item.get("warnings", [])
                if isinstance(warning, str)
            ],
            error=item.get("error"),
            metadata=self._dict(item.get("metadata")),
        )

    def _step_state_from_plain(self, item: dict[str, Any]) -> StepExecutionState:
        return StepExecutionState(
            step_id=str(item["step_id"]),
            status=str(item.get("status", "pending")),
            attempt=int(item.get("attempt", 0)),
            started_at=self._optional_datetime(item.get("started_at")),
            completed_at=self._optional_datetime(item.get("completed_at")),
            input_snapshot=self._dict(item.get("input_snapshot")),
            output=self._dict(item.get("output")),
            error=item.get("error"),
            validation=self._dict(item.get("validation")),
            next_retry_at=self._optional_datetime(item.get("next_retry_at")),
            metadata=self._dict(item.get("metadata")),
        )

    def _dict(self, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now().astimezone()

    def _optional_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        return self._datetime(value)

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    def _event_bus(self) -> Any | None:
        core = getattr(self.capability_runtime, "core", None)
        return getattr(core, "events", None)
