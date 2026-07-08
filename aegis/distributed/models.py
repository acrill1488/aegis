from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MachineRecord:
    machine_id: str
    hostname: str
    os: str
    version: str
    capabilities: list[str]
    connected: bool = False
    last_seen: datetime | None = None
    session_id: str | None = None
    metadata: dict = field(default_factory=dict)
