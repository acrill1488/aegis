"""Prompt compiler public contracts."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PromptBlock:
    """A named prompt fragment with deterministic ordering controls."""

    name: str
    content: str
    priority: int = 100
    enabled: bool = True


@dataclass(slots=True)
class PromptPackage:
    """Compiled prompt payload ready for runtime adapters."""

    system: str
    context: str
    user: str
    metadata: dict[str, Any] = field(default_factory=dict)
