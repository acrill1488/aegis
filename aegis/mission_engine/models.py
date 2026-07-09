from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MissionNode:
    id: str
    skill_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Mission:
    id: str
    goal: str
    status: str = "created"
    priority: int = 50
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    workspace_path: str = ""
    graph: list[MissionNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionResult:
    success: bool
    completed_nodes: list[str] = field(default_factory=list)
    failed_node: str | None = None
    report_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
