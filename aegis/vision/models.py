"""Shared Vision data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass
class Bounds:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class VisionElement:
    id: str = field(default_factory=lambda: _id("vision_element"))
    type: str = "text"
    text: str = ""
    bounds: Bounds | None = None
    confidence: float = 0.0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VisionSnapshot:
    id: str = field(default_factory=lambda: _id("vision_snapshot"))
    source: str = "desktop"
    image_path: str = ""
    width: int = 0
    height: int = 0
    elements: list[VisionElement] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
