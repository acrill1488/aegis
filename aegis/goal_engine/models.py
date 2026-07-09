from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Goal:
    id: str
    text: str
    intent: str
    confidence: float
    selected_skill: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
