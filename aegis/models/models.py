from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelRecord:
    id: str
    name: str
    provider: str
    model_ref: str
    task_types: list[str]
    context_window: int | None = None
    input_modalities: list[str] = field(default_factory=list)
    output_modalities: list[str] = field(default_factory=list)
    quantization: str | None = None
    ram_required_gb: float | None = None
    vram_required_gb: float | None = None
    quality_tier: str = "unknown"
    speed_tier: str = "unknown"
    license: str | None = None
    enabled: bool = True
    metadata: dict = field(default_factory=dict)
