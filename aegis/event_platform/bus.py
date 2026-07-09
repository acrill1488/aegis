from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from aegis.serialization import to_plain

from .models import AegisEvent, EventReceipt
from .store import EventStore


EventHandler = Callable[[AegisEvent], None]


class EventBus:
    """Central event bus that persists events before fan-out."""

    def __init__(self, store: EventStore | None = None):
        self.store = store or EventStore()
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def publish(self, event: AegisEvent) -> EventReceipt:
        self.store.append(event)
        delivered = 0
        failed = 0
        for handler in list(self._handlers.get(event.type, [])):
            try:
                handler(event)
                delivered += 1
            except Exception as exc:
                failed += 1
                self._record_handler_failure(event, handler, exc)
        return EventReceipt(event_id=event.id, delivered=delivered, failed=failed)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type)
        if not handlers:
            return
        self._handlers[event_type] = [item for item in handlers if item != handler]

    def list_subscribers(self) -> dict[str, int]:
        return {event_type: len(handlers) for event_type, handlers in sorted(self._handlers.items())}

    def _record_handler_failure(
        self,
        event: AegisEvent,
        handler: EventHandler,
        exc: Exception,
    ) -> None:
        if event.type == "event.handler_failed":
            return
        failure = AegisEvent.create(
            "event.handler_failed",
            "event_platform.bus",
            severity="error",
            project_id=event.project_id,
            mission_id=event.mission_id,
            skill_id=event.skill_id,
            correlation_id=event.correlation_id,
            payload={
                "event_id": event.id,
                "event_type": event.type,
                "handler": getattr(handler, "__qualname__", repr(handler)),
                "error": str(exc),
            },
            metadata={"failed_event": to_plain(event.to_dict())},
        )
        try:
            self.store.append(failure)
        except Exception:
            return
