"""Context Builder data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextSource:
    type: str
    title: str
    content: str
    score: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ContextBundle:
    user_prompt: str
    sources: list[ContextSource]
    summary: str = ""
    metadata: dict = field(default_factory=dict)
