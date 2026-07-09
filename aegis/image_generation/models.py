"""Image Generation Runtime data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    steps: int = 20
    seed: int | None = None
    style: str = ""
    output_dir: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenerationResult:
    success: bool
    image_paths: list[str] = field(default_factory=list)
    provider: str = ""
    prompt: str = ""
    seed: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
