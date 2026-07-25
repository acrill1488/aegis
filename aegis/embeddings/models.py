"""Provider-neutral embedding request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EmbeddingRequest:
    texts: str | list[str]
    provider: str | None = None
    normalize: bool | None = None
    batch_size: int | None = None
    device: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    execution: str | None = None
    node: str | None = None


@dataclass(frozen=True)
class EmbeddingVector:
    index: int
    text: str
    vector: list[float]
    dimensions: int
    norm: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingResult:
    provider: str
    model: str
    vectors: list[EmbeddingVector]
    dimensions: int
    normalized: bool
    device: str
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
