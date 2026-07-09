from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return utc_now()


@dataclass
class ReflectionRecommendation:
    id: str = field(default_factory=lambda: f"reflection_rec_{uuid4().hex}")
    type: str = ""
    target: str = ""
    priority: str = "medium"
    reason: str = ""
    confidence: float = 0.3
    status: str = "open"
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "ReflectionRecommendation":
        return cls(
            id=str(item.get("id") or f"reflection_rec_{uuid4().hex}"),
            type=str(item.get("type") or ""),
            target=str(item.get("target") or ""),
            priority=str(item.get("priority") or "medium"),
            reason=str(item.get("reason") or ""),
            confidence=float(item.get("confidence", 0.3)),
            status=str(item.get("status") or "open"),
            created_at=parse_datetime(item.get("created_at")),
            metadata=dict(item.get("metadata") or {}),
        )


@dataclass
class ReflectionReport:
    id: str = field(default_factory=lambda: f"reflection_report_{uuid4().hex}")
    mission_id: str = ""
    project_id: str | None = None
    goal: str = ""
    summary: str = ""
    success: bool = False
    duration: float | None = None
    recovery_count: int = 0
    warnings: list[str] = field(default_factory=list)
    recommendations: list[ReflectionRecommendation] = field(default_factory=list)
    confidence: float = 0.3
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "ReflectionReport":
        recommendations = item.get("recommendations") or []
        if not isinstance(recommendations, list):
            recommendations = []
        warnings = item.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = []
        return cls(
            id=str(item.get("id") or f"reflection_report_{uuid4().hex}"),
            mission_id=str(item.get("mission_id") or ""),
            project_id=(
                str(item.get("project_id"))
                if item.get("project_id") is not None
                else None
            ),
            goal=str(item.get("goal") or ""),
            summary=str(item.get("summary") or ""),
            success=bool(item.get("success", False)),
            duration=(
                float(item["duration"])
                if item.get("duration") is not None
                else None
            ),
            recovery_count=int(item.get("recovery_count", 0)),
            warnings=[str(warning) for warning in warnings],
            recommendations=[
                ReflectionRecommendation.from_dict(recommendation)
                for recommendation in recommendations
                if isinstance(recommendation, dict)
            ],
            confidence=float(item.get("confidence", 0.3)),
            created_at=parse_datetime(item.get("created_at")),
            metadata=dict(item.get("metadata") or {}),
        )
