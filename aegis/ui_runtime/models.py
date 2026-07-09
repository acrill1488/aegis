from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UIElement:
    id: str
    role: str = ""
    name: str = ""
    description: str = ""
    text: str = ""
    bounds: dict[str, float] | None = None
    visible: bool = True
    enabled: bool = True
    children: list["UIElement"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UITree:
    root: UIElement
    provider: str
    source: str
