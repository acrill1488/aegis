from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InferenceResult:
    success: bool
    task_type: str
    model_id: str | None = None
    provider_id: str | None = None
    output: dict = field(default_factory=dict)
    error: str | None = None
    latency_ms: float | None = None
    metadata: dict = field(default_factory=dict)
