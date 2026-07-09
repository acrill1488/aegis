from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegis.serialization import to_plain

from .models import ExecutionGraph, Plan, PlanStep, Task


DEFAULT_PLANNING_PATH = Path(r"F:\AI_WORKSPACE\planning")


class TaskPlanningRuntime:
    """Persistent Task Planning Runtime v1 stage 1.

    Stage 1 stores Tasks and creates declarative empty Plans only. It does not
    decompose work, validate graphs, or invoke capabilities.
    """

    def __init__(self, path: str | Path = DEFAULT_PLANNING_PATH):
        self.path = Path(path)
        self.tasks_path = self.path / "tasks.json"
        self.plans_path = self.path / "plans.json"
        self._tasks: dict[str, Task] = {}
        self._plans: dict[str, Plan] = {}
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
    ) -> Plan:
        if task_id not in self._tasks:
            raise KeyError(f"Task not found: {task_id}")

        plan = Plan(
            id=plan_id or self._new_id("plan"),
            task_id=task_id,
            graph=ExecutionGraph(),
            metadata=dict(metadata or {}),
        )
        self._plans[plan.id] = plan
        self._save_plans()
        return plan

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def get_plan(self, plan_id: str) -> Plan | None:
        return self._plans.get(plan_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def list_plans(self) -> list[Plan]:
        return list(self._plans.values())

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok" if self._persistence_available else "degraded",
            "persistence_available": self._persistence_available,
            "path": str(self.path),
            "tasks": len(self._tasks),
            "plans": len(self._plans),
        }

    def _ensure_files(self) -> None:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            for file_path in (self.tasks_path, self.plans_path):
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
        self._save_tasks()
        self._save_plans()

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

    def _dict(self, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now().astimezone()

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"
