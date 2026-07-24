"""Provider-local normalized PaddleOCR models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PaddleOCRLine:
    text: str
    confidence: float
    bounding_box: list[list[float]] = field(default_factory=list)


@dataclass(frozen=True)
class PaddleOCRResult:
    text: str
    lines: list[PaddleOCRLine]
    confidence: float | None
    language: str
    provider: str
    duration_ms: float
    device: str
    metadata: dict[str, Any] = field(default_factory=dict)

