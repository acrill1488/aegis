"""Provider-neutral OCR Runtime data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OCRBlock:
    """A single recognized document block."""

    text: str
    bbox: list[float] = field(default_factory=list)
    role: str = "text"
    page: int = 1
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRTable:
    """Structured table extracted by an OCR provider."""

    page: int = 1
    rows: list[list[str]] = field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRResult:
    """Normalized OCR result independent from any concrete OCR provider."""

    provider: str
    language: str = "unknown"
    pages: list[dict[str, Any]] = field(default_factory=list)
    text: str = ""
    blocks: list[OCRBlock | dict[str, Any]] = field(default_factory=list)
    tables: list[OCRTable | dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    confidence: float | None = None
    processing_time: float = 0.0
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source: str | dict[str, Any] = ""
