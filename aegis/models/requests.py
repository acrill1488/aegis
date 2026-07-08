from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelRequest:
    task_type: str
    input: dict
    prompt_profile: str | None = None
    constraints: dict = field(default_factory=dict)
    timeout_ms: int = 120000
    trace_id: str | None = None
    metadata: dict = field(default_factory=dict)
