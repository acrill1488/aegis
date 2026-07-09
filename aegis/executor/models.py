from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionStep:
    id: str
    description: str = ""
    observe: Any = None
    reason: Any = None
    action: Any = None
    validate: Any = None
    retry_limit: int = 0
    timeout: int | dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    goal: str
    steps: list[ExecutionStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "created"
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionResult:
    success: bool
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
