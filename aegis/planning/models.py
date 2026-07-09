from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Task:
    id: str
    goal: str
    priority: int = 50
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanStep:
    id: str
    capability_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    timeout: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionGraph:
    nodes: list[PlanStep] = field(default_factory=list)
    edges: list[list[str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    id: str
    task_id: str
    status: str = "created"
    graph: ExecutionGraph = field(default_factory=ExecutionGraph)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepExecutionState:
    step_id: str
    status: str = "pending"
    attempt: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    validation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanExecution:
    execution_id: str
    plan_id: str
    task_id: str
    status: str = "created"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    step_states: dict[str, StepExecutionState] = field(default_factory=dict)
    trace_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
