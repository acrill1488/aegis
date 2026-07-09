from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, List
from uuid import uuid4

@dataclass
class PlanStep:
    id: int
    title: str
    description: str
    tool: Optional[str] = None
    status: str = "pending"

@dataclass
class ExecutionPlan:
    task_id: str
    goal: str
    steps: List[PlanStep]
    raw_response: Optional[str] = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PlannerContext:
    goal: str
    project_id: str | None = None
    knowledge_hits: list[dict[str, Any]] = field(default_factory=list)
    reflection_reports: list[dict[str, Any]] = field(default_factory=list)
    memory_hits: list[dict[str, Any]] = field(default_factory=list)
    recent_missions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerStep:
    id: str
    title: str
    skill_id: str
    priority: int = 50
    dependencies: list[str] = field(default_factory=list)
    estimated_duration: float | None = None
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerPlan:
    id: str = field(default_factory=lambda: f"plan_{uuid4().hex}")
    goal: str = ""
    context: PlannerContext | None = None
    graph: Any | None = None
    status: str = "created"
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    validated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
