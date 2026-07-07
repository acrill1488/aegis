"""Data models for the Retriever pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedDocument:
    title: str
    url: str
    source: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class RetrieverResult:
    query: str
    documents: list[RetrievedDocument]
    summary: str = ""
    gaps: list[str] = field(default_factory=list)
