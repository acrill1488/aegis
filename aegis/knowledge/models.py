"""Data models for Knowledge Engine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KnowledgeSource:
    type: str
    title: str
    content: str
    url: str | None = None
    score: float = 1.0
    valid: bool = True
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class KnowledgeBundle:
    query: str
    sources: list[KnowledgeSource]
    summary: str = ""
    gaps: list[str] = field(default_factory=list)
