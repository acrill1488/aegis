import os
from collections.abc import Callable
from pathlib import Path

from aegis.event_platform import EventPlatformRuntime

from .models import AegisEvent, EventReceipt


class EventBus:
    """Compatibility wrapper over the v1 Event Platform."""

    def __init__(
        self,
        max_history: int = 200,
        history_file: str | os.PathLike[str] = r"F:\AI_WORKSPACE\events\events.json",
        platform: EventPlatformRuntime | None = None,
    ):
        self._max_history = max_history
        self._history_file = Path(history_file)
        self.platform = platform or EventPlatformRuntime()

    def subscribe(self, event_type: str, handler: Callable[[AegisEvent], None]) -> None:
        self.platform.bus.subscribe(event_type, handler)

    def unsubscribe(self, event_type: str, handler: Callable[[AegisEvent], None]) -> None:
        self.platform.bus.unsubscribe(event_type, handler)

    def list_subscribers(self) -> dict[str, int]:
        return self.platform.bus.list_subscribers()

    def publish(
        self,
        event_type: str,
        source: str,
        payload: dict | None = None,
        trace_id: str | None = None,
        **context,
    ) -> EventReceipt:
        return self.platform.publish(
            event_type,
            source,
            payload,
            correlation_id=trace_id,
            **context,
        )

    def history(self, limit: int = 50) -> list[AegisEvent]:
        return list(reversed(self.platform.list(limit=limit)))
