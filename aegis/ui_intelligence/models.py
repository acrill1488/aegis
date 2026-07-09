from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UIElement:
    id: str
    role: str
    name: str = ""
    text: str = ""
    selector: str | dict | None = None
    visible: bool = True
    enabled: bool = True
    confidence: float = 1.0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UIObservation:
    source: str
    url: str | None = None
    title: str | None = None
    application: str | None = None
    focused_element: UIElement | None = None
    elements: list[UIElement] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
