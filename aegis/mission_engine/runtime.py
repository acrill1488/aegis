from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aegis.goal_engine.models import Goal
from aegis.serialization import to_plain
from aegis.skill_engine import SkillEngineRuntime

from .models import Mission, MissionNode, MissionResult
from .planner import MissionPlanner
from .registry import MissionRegistry


class MissionRuntime:
    """Creates and executes multi-skill Mission graphs."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        skill_engine: SkillEngineRuntime | None = None,
        planner: MissionPlanner | None = None,
        registry: MissionRegistry | None = None,
    ):
        self.core = core
        self.skill_engine = skill_engine or getattr(core, "skill_engine", None)
        if self.skill_engine is None:
            self.skill_engine = SkillEngineRuntime(core)
        self.planner = planner or MissionPlanner()
        self.registry = registry or MissionRegistry()

    def create(
        self,
        goal: Goal | str,
        *,
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
    ) -> Mission:
        if isinstance(goal, Goal):
            mission_id = self.planner._new_id()
            workspace = self.registry.allocate_workspace(mission_id)
            mission = self.planner.create_from_goal(
                goal,
                priority=priority,
                mission_id=mission_id,
                workspace_path=str(workspace),
                metadata=metadata,
            )
        else:
            mission_id = self.planner._new_id()
            workspace = self.registry.allocate_workspace(mission_id)
            mission = Mission(
                id=mission_id,
                goal=str(goal),
                priority=priority,
                workspace_path=str(workspace),
                metadata=dict(metadata or {}),
            )
        return self.registry.save(mission)

    def run(self, mission_or_id: Mission | str) -> MissionResult:
        mission = self._resolve_mission(mission_or_id)
        if mission.status == "cancelled":
            return MissionResult(
                success=False,
                completed_nodes=self._completed_nodes(mission),
                failed_node=None,
                report_path=str(Path(mission.workspace_path) / "report.md"),
                error="Mission is cancelled",
            )

        self._validate_graph(mission.graph)
        mission.status = "running"
        mission.started_at = mission.started_at or self._now()
        self.registry.save(mission)

        failed_node: str | None = None
        error: str | None = None
        completed_nodes: list[str] = []

        while True:
            pending = [node for node in mission.graph if node.status == "pending"]
            if not pending:
                break

            ready = [
                node
                for node in pending
                if all(self._node_status(mission, dependency) == "completed" for dependency in node.dependencies)
            ]
            if not ready:
                failed_node = pending[0].id
                error = "Mission graph has blocked nodes"
                pending[0].status = "blocked"
                break

            for node in ready:
                result = self._run_node(node)
                self.registry.save(mission)
                if result.success:
                    completed_nodes.append(node.id)
                    continue
                failed_node = node.id
                error = result.error
                break
            if failed_node is not None:
                break

        mission.completed_at = self._now()
        if failed_node is None:
            mission.status = "completed"
            success = True
        else:
            mission.status = "failed"
            success = False
        self.registry.save(mission)
        report_path = self._write_report(mission, error=error)
        self.registry.save(mission)
        return MissionResult(
            success=success,
            completed_nodes=self._completed_nodes(mission),
            failed_node=failed_node,
            report_path=str(report_path),
            error=error,
        )

    def status(self, mission_id: str) -> dict[str, Any]:
        mission = self._resolve_mission(mission_id)
        return {
            "id": mission.id,
            "status": mission.status,
            "completed_nodes": self._completed_nodes(mission),
            "failed_nodes": [
                node.id for node in mission.graph if node.status in {"failed", "blocked"}
            ],
            "workspace_path": mission.workspace_path,
        }

    def cancel(self, mission_id: str) -> Mission:
        mission = self._resolve_mission(mission_id)
        if mission.status not in {"completed", "failed"}:
            mission.status = "cancelled"
            mission.completed_at = self._now()
            self.registry.save(mission)
            self._write_report(mission, error="Mission cancelled")
        return mission

    def show(self, mission_id: str) -> Mission:
        return self._resolve_mission(mission_id)

    def list(self) -> list[Mission]:
        return self.registry.list()

    def _run_node(self, node: MissionNode):
        node.status = "running"
        started_at = self._now()
        try:
            result = self.skill_engine.run(node.skill_id, node.inputs)
        except Exception as exc:
            node.status = "failed"
            node.outputs = {}
            node.metadata["error"] = str(exc)
            node.metadata["started_at"] = started_at
            node.metadata["completed_at"] = self._now()
            return MissionResult(success=False, failed_node=node.id, error=str(exc))

        node.outputs = to_plain(getattr(result, "output", {}))
        node.metadata["skill_result"] = result
        node.metadata["started_at"] = getattr(result, "started_at", started_at)
        node.metadata["completed_at"] = getattr(result, "completed_at", self._now())
        if getattr(result, "success", False):
            node.status = "completed"
            return MissionResult(success=True, completed_nodes=[node.id])

        node.status = "failed"
        error = getattr(result, "error", None) or "Skill execution failed"
        node.metadata["error"] = error
        return MissionResult(success=False, failed_node=node.id, error=error)

    def _write_report(self, mission: Mission, *, error: str | None) -> Path:
        path = Path(mission.workspace_path) / "report.md"
        duration = ""
        if mission.started_at and mission.completed_at:
            duration = str(mission.completed_at - mission.started_at)
        skills = "\n".join(
            f"- {node.skill_id}: {node.status}" for node in mission.graph
        ) or "- none"
        errors = error or "\n".join(
            str(node.metadata.get("error"))
            for node in mission.graph
            if node.metadata.get("error")
        )
        text = (
            f"# Mission Report\n\n"
            f"## Goal\n{mission.goal}\n\n"
            f"## Skills\n{skills}\n\n"
            f"## Execution time\n{duration or 'not started'}\n\n"
            f"## Result\n{mission.status}\n\n"
            f"## Errors\n{errors or 'None'}\n"
        )
        path.write_text(text, encoding="utf-8")
        return path

    def _validate_graph(self, graph: list[MissionNode]) -> None:
        node_ids = {node.id for node in graph}
        if len(node_ids) != len(graph):
            raise ValueError("Mission graph contains duplicate node ids")
        for node in graph:
            missing = [dependency for dependency in node.dependencies if dependency not in node_ids]
            if missing:
                raise ValueError(f"Mission node {node.id} has missing dependencies: {missing}")
        self._assert_acyclic(graph)

    def _assert_acyclic(self, graph: list[MissionNode]) -> None:
        nodes = {node.id: node for node in graph}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            if node_id in visiting:
                raise ValueError("Mission graph must be a DAG")
            visiting.add(node_id)
            for dependency in nodes[node_id].dependencies:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in nodes:
            visit(node_id)

    def _resolve_mission(self, mission_or_id: Mission | str) -> Mission:
        if isinstance(mission_or_id, Mission):
            return mission_or_id
        mission = self.registry.get(mission_or_id)
        if mission is None:
            raise KeyError(f"Mission not found: {mission_or_id}")
        return mission

    def _node_status(self, mission: Mission, node_id: str) -> str | None:
        for node in mission.graph:
            if node.id == node_id:
                return node.status
        return None

    def _completed_nodes(self, mission: Mission) -> list[str]:
        return [node.id for node in mission.graph if node.status == "completed"]

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
