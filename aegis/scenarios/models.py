from __future__ import annotations

from dataclasses import field, dataclass
from datetime import datetime
from typing import Any


@dataclass
class ScenarioStep:
    id: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    expect: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    id: str
    name: str
    description: str = ""
    steps: list[ScenarioStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioRunResult:
    scenario_id: str
    success: bool
    started_at: datetime
    completed_at: datetime
    step_results: list[dict[str, Any]]
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
