from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


ORCHESTRATOR_STATUSES = {
    "queued",
    "ready",
    "running",
    "waiting",
    "paused",
    "completed",
    "failed",
    "cancelled",
}

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
RUNNABLE_STATUSES = {"queued", "ready"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OrchestratorJob:
    id: str
    mission_id: str
    project_id: str | None = None
    goal: str = ""
    status: str = "queued"
    priority: int = 50
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dependencies: list[str] = field(default_factory=list)
    worker_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        mission_id: str,
        *,
        project_id: str | None = None,
        goal: str = "",
        priority: int = 50,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "OrchestratorJob":
        return cls(
            id=f"job_{uuid4().hex}",
            mission_id=mission_id,
            project_id=project_id,
            goal=goal,
            priority=priority,
            dependencies=list(dependencies or []),
            metadata=dict(metadata or {}),
        )

    def validate(self) -> None:
        if self.status not in ORCHESTRATOR_STATUSES:
            raise ValueError(f"Unknown orchestrator job status: {self.status}")
        if not self.id:
            raise ValueError("Orchestrator job id is required")
        if not self.mission_id:
            raise ValueError("Orchestrator job mission_id is required")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
            "goal": self.goal,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "dependencies": list(self.dependencies),
            "worker_id": self.worker_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrchestratorJob":
        job = cls(
            id=str(data["id"]),
            mission_id=str(data["mission_id"]),
            project_id=_optional_str(data.get("project_id")),
            goal=str(data.get("goal") or ""),
            status=str(data.get("status") or "queued"),
            priority=int(data.get("priority", 50)),
            created_at=_parse_datetime(data.get("created_at")),
            started_at=_optional_datetime(data.get("started_at")),
            completed_at=_optional_datetime(data.get("completed_at")),
            dependencies=[str(item) for item in data.get("dependencies") or []],
            worker_id=_optional_str(data.get("worker_id")),
            metadata=dict(data.get("metadata") or {}),
        )
        job.validate()
        return job


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return utc_now()


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime(value)
