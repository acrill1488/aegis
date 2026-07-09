from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MCPServerRecord:
    id: str
    name: str
    command: str
    args: list[str]
    env: dict = field(default_factory=dict)
    enabled: bool = True
    status: str = "unknown"
    capabilities: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
