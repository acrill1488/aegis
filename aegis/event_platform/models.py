from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aegis.serialization import to_plain


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AegisEvent:
    id: str
    type: str
    timestamp: datetime
    source: str
    severity: str = "info"
    project_id: str | None = None
    mission_id: str | None = None
    skill_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        type: str,
        source: str,
        *,
        payload: dict[str, Any] | None = None,
        severity: str = "info",
        project_id: str | None = None,
        mission_id: str | None = None,
        skill_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AegisEvent":
        return cls(
            id=str(uuid4()),
            type=type,
            timestamp=utc_now(),
            source=source,
            severity=severity,
            project_id=project_id,
            mission_id=mission_id,
            skill_id=skill_id,
            correlation_id=correlation_id,
            payload=dict(to_plain(payload or {}) or {}),
            metadata=dict(to_plain(metadata or {}) or {}),
        )

    @property
    def created_at(self) -> datetime:
        return self.timestamp

    @property
    def trace_id(self) -> str | None:
        return self.correlation_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "severity": self.severity,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "skill_id": self.skill_id,
            "correlation_id": self.correlation_id,
            "payload": to_plain(self.payload),
            "metadata": to_plain(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AegisEvent":
        timestamp = data.get("timestamp") or data.get("created_at")
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            timestamp=_parse_datetime(timestamp),
            source=str(data["source"]),
            severity=str(data.get("severity") or "info"),
            project_id=_optional_str(data.get("project_id")),
            mission_id=_optional_str(data.get("mission_id")),
            skill_id=_optional_str(data.get("skill_id")),
            correlation_id=_optional_str(data.get("correlation_id") or data.get("trace_id")),
            payload=dict(data.get("payload") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class EventReceipt:
    event_id: str
    delivered: int
    failed: int


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return utc_now()
