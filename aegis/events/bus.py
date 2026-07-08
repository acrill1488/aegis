import json
import os
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from aegis.serialization import to_json, to_plain

from .models import AegisEvent, EventReceipt


class EventBus:
    """Event bus for decoupled internal module notifications."""

    def __init__(
        self,
        max_history: int = 200,
        history_file: str | os.PathLike[str] = r"F:\AI_WORKSPACE\events\events.json",
    ):
        self._max_history = max_history
        self._history_file = Path(history_file)
        self._handlers: dict[str, list[Callable[[AegisEvent], None]]] = defaultdict(list)
        self._history: deque[AegisEvent] = deque(maxlen=max_history)
        self._ensure_history_file()
        self._load_history()

    def subscribe(self, event_type: str, handler: Callable[[AegisEvent], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(
        self,
        event_type: str,
        source: str,
        payload: dict | None = None,
        trace_id: str | None = None,
    ) -> EventReceipt:
        event = AegisEvent(
            id=str(uuid.uuid4()),
            type=event_type,
            source=source,
            payload=to_plain(dict(payload or {})),
            created_at=datetime.now(),
            trace_id=trace_id,
        )
        self._history.append(event)

        delivered = 0
        failed = 0
        for handler in list(self._handlers.get(event_type, [])):
            try:
                handler(event)
                delivered += 1
            except Exception:
                failed += 1

        self._save_history()
        return EventReceipt(event_id=event.id, delivered=delivered, failed=failed)

    def history(self, limit: int = 50) -> list[AegisEvent]:
        if limit <= 0:
            return []
        events = list(self._history)
        return events[-limit:]

    def _ensure_history_file(self) -> None:
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._history_file.exists():
            self._history_file.write_text("[]", encoding="utf-8")

    def _load_history(self) -> None:
        try:
            data = json.loads(self._history_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []

        if not isinstance(data, list):
            data = []

        for item in data[-self._max_history :]:
            if not isinstance(item, dict):
                continue
            try:
                event = AegisEvent(
                    id=str(item["id"]),
                    type=str(item["type"]),
                    source=str(item["source"]),
                    payload=dict(item.get("payload") or {}),
                    created_at=datetime.fromisoformat(str(item["created_at"])),
                    trace_id=item.get("trace_id"),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._history.append(event)

    def _save_history(self) -> None:
        data = [
            {
                "id": event.id,
                "type": event.type,
                "source": event.source,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
                "trace_id": event.trace_id,
            }
            for event in self._history
        ]
        self._history_file.write_text(
            to_json(data),
            encoding="utf-8",
        )
