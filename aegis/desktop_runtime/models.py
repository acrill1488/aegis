from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DesktopWindow:
    id: str
    title: str
    process_name: str
    pid: int
    active: bool
    visible: bool
    bounds: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DesktopApp:
    name: str
    executable: str
    pid: int
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)
