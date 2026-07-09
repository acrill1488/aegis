from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


EXPERIENCE_TYPES = {
    "recovery.selector_patch",
    "recovery.success",
    "recovery.failure",
    "skill.success",
    "skill.failure",
    "mission.success",
    "mission.failure",
    "browser.selector",
    "performance.metric",
    "reflection.report",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OperationalExperience:
    id: str = field(default_factory=lambda: f"opmem_{uuid4().hex}")
    type: str = ""
    source: str = ""
    summary: str = ""
    created_at: datetime = field(default_factory=utc_now)
    confidence: float = 1.0
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "OperationalExperience":
        created_at = item.get("created_at")
        if isinstance(created_at, datetime):
            parsed_created_at = created_at
        elif isinstance(created_at, str) and created_at:
            parsed_created_at = datetime.fromisoformat(created_at)
        else:
            parsed_created_at = utc_now()
        return cls(
            id=str(item.get("id") or f"opmem_{uuid4().hex}"),
            type=str(item.get("type") or ""),
            source=str(item.get("source") or ""),
            summary=str(item.get("summary") or ""),
            created_at=parsed_created_at,
            confidence=float(item.get("confidence", 1.0)),
            data=dict(item.get("data") or {}),
            metadata=dict(item.get("metadata") or {}),
        )
