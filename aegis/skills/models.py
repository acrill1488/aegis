"""Data models for AEGIS skills."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillResult:
    success: bool
    skill: str
    output: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SkillDescriptor:
    name: str
    description: str
    capabilities: list[str]
    enabled: bool = True
