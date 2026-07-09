from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import Mission, MissionNode


DEFAULT_MISSION_ROOT = Path(r"F:\AI_WORKSPACE\missions")


class MissionRegistry:
    """File-backed registry for Mission workspaces."""

    def __init__(self, root: str | Path = DEFAULT_MISSION_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def allocate_workspace(self, mission_id: str) -> Path:
        workspace = self.root / mission_id
        for child in ("logs", "outputs", "screenshots", "downloads"):
            (workspace / child).mkdir(parents=True, exist_ok=True)
        return workspace

    def save(self, mission: Mission) -> Mission:
        workspace = Path(mission.workspace_path) if mission.workspace_path else self.allocate_workspace(mission.id)
        mission.workspace_path = str(workspace)
        self.allocate_workspace(mission.id)
        self._write_json(workspace / "mission.json", mission)
        self._write_json(workspace / "graph.json", {"nodes": mission.graph})
        goal = mission.metadata.get("goal", mission.goal)
        self._write_json(workspace / "goal.json", goal)
        report_path = workspace / "report.md"
        if not report_path.exists():
            report_path.write_text("", encoding="utf-8")
        return mission

    def get(self, mission_id: str) -> Mission | None:
        path = self.root / mission_id / "mission.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            return self._mission_from_plain(data)
        except (KeyError, TypeError, ValueError):
            return None

    def list(self) -> list[Mission]:
        missions = []
        for path in sorted(self.root.glob("mission_*/mission.json")):
            mission = self.get(path.parent.name)
            if mission is not None:
                missions.append(mission)
        return missions

    def _write_json(self, path: Path, value: Any) -> None:
        path.write_text(
            json.dumps(to_plain(value), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _mission_from_plain(self, data: dict[str, Any]) -> Mission:
        graph = data.get("graph") or []
        if not isinstance(graph, list):
            graph = []
        return Mission(
            id=str(data["id"]),
            goal=str(data["goal"]),
            status=str(data.get("status", "created")),
            priority=int(data.get("priority", 50)),
            created_at=self._datetime(data.get("created_at")),
            started_at=self._optional_datetime(data.get("started_at")),
            completed_at=self._optional_datetime(data.get("completed_at")),
            workspace_path=str(data.get("workspace_path") or self.root / str(data["id"])),
            graph=[
                self._node_from_plain(node)
                for node in graph
                if isinstance(node, dict)
            ],
            metadata=dict(data.get("metadata") or {}),
        )

    def _node_from_plain(self, data: dict[str, Any]) -> MissionNode:
        dependencies = data.get("dependencies") or []
        if not isinstance(dependencies, list):
            dependencies = []
        return MissionNode(
            id=str(data["id"]),
            skill_id=str(data["skill_id"]),
            inputs=dict(data.get("inputs") or {}),
            outputs=dict(data.get("outputs") or {}),
            dependencies=[str(dependency) for dependency in dependencies],
            status=str(data.get("status", "pending")),
            metadata=dict(data.get("metadata") or {}),
        )

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
