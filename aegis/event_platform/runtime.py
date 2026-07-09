from __future__ import annotations

from collections import Counter
from typing import Any

from aegis.serialization import to_plain

from .bus import EventBus
from .models import AegisEvent, EventReceipt
from .store import EventStore


class EventPlatformRuntime:
    """Runtime facade for publishing, querying, timeline, replay, and stats."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        store: EventStore | None = None,
        bus: EventBus | None = None,
    ):
        self.core = core
        self.store = store or EventStore()
        self.bus = bus or EventBus(self.store)

    def publish(
        self,
        type: str,
        source: str,
        payload: dict[str, Any] | None = None,
        **context: Any,
    ) -> EventReceipt:
        event = self.create_event(type, source, payload=payload, **context)
        return self.bus.publish(event)

    def create_event(
        self,
        type: str,
        source: str,
        payload: dict[str, Any] | None = None,
        **context: Any,
    ) -> AegisEvent:
        context = dict(context)
        metadata = dict(to_plain(context.pop("metadata", {}) or {}) or {})
        severity = str(context.pop("severity", "info") or "info")
        project_id = context.pop("project_id", None)
        if project_id is None:
            project_id = self._active_project_id()
        return AegisEvent.create(
            type,
            source,
            payload=payload,
            severity=severity,
            project_id=project_id,
            mission_id=context.pop("mission_id", None),
            skill_id=context.pop("skill_id", None),
            correlation_id=context.pop("correlation_id", None) or context.pop("trace_id", None),
            metadata={**metadata, **to_plain(context)},
        )

    def list(
        self,
        limit: int = 100,
        type: str | None = None,
        mission_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
    ) -> list[AegisEvent]:
        return self.store.list(
            limit=limit,
            type=type,
            mission_id=mission_id,
            project_id=project_id,
            correlation_id=correlation_id,
        )

    def timeline(
        self,
        mission_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
    ) -> list[AegisEvent]:
        return self.store.timeline(
            mission_id=mission_id,
            project_id=project_id,
            correlation_id=correlation_id,
        )

    def replay(
        self,
        correlation_id: str | None = None,
        mission_id: str | None = None,
    ) -> list[AegisEvent]:
        return self.store.replay(correlation_id=correlation_id, mission_id=mission_id)

    def stats(self) -> dict[str, Any]:
        events = self.store.list(limit=1_000_000)
        by_type = Counter(event.type for event in events)
        by_source = Counter(event.source for event in events)
        by_severity = Counter(event.severity for event in events)
        latest = max(events, key=lambda item: item.timestamp, default=None)
        return {
            "path": str(self.store.root),
            "total": len(events),
            "by_type": dict(sorted(by_type.items())),
            "by_source": dict(sorted(by_source.items())),
            "by_severity": dict(sorted(by_severity.items())),
            "latest": to_plain(latest.to_dict() if latest else None),
            "subscribers": self.bus.list_subscribers(),
        }

    def _active_project_id(self) -> str | None:
        project_runtime = getattr(self.core, "project_runtime", None)
        get_active = getattr(project_runtime, "get_active", None)
        if not callable(get_active):
            return None
        try:
            project = get_active()
        except Exception:
            return None
        return getattr(project, "id", None) if project is not None else None
