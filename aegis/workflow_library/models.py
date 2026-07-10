"""Workflow Library data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowTemplate:
    id: str
    name: str
    path: str
    category: str = "general"
    task_type: str = "txt2img"
    model_family: str = ""
    required_models: list[str] = field(default_factory=list)
    supported_inputs: list[str] = field(default_factory=lambda: ["prompt"])
    default_width: int = 1024
    default_height: int = 1024
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowValidationResult:
    workflow_id: str
    success: bool
    missing_models: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
