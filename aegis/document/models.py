"""Structured Document contract models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BBox = list[float]


@dataclass
class DocumentBlock:
    """A normalized text block inside a document page."""

    id: str
    bbox: BBox = field(default_factory=list)
    text: str = ""
    role: str = "text"
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentTable:
    """A normalized table inside a document page."""

    rows: list[list[str]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    cells: list[dict[str, Any]] = field(default_factory=list)
    bbox: BBox = field(default_factory=list)
    confidence: float | None = None


@dataclass
class DocumentFigure:
    """A normalized figure inside a document page."""

    bbox: BBox = field(default_factory=list)
    caption: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentPage:
    """A single normalized document page."""

    number: int
    width: float | None = None
    height: float | None = None
    rotation: float = 0.0
    blocks: list[DocumentBlock] = field(default_factory=list)
    tables: list[DocumentTable] = field(default_factory=list)
    figures: list[DocumentFigure] = field(default_factory=list)
    reading_order: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredDocument:
    """Official internal document contract between OCR and later AI platforms."""

    id: str
    source: str | dict[str, Any]
    provider: str
    created_at: str
    language: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    plain_text: str = ""
    pages: list[DocumentPage] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
