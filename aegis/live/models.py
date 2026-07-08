from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContextEntry:
    key: str
    value: dict
    source: str
    updated_at: datetime
    ttl_seconds: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ContextSnapshot:
    entries: list[ContextEntry]
    created_at: datetime
    metadata: dict = field(default_factory=dict)
