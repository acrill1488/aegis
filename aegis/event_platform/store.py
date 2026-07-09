from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import AegisEvent


DEFAULT_EVENT_ROOT = Path(r"F:\AI_WORKSPACE\events")


class EventStore:
    """Append-only JSONL store for the universal AEGIS event log."""

    def __init__(self, root: str | Path = DEFAULT_EVENT_ROOT):
        self.root = Path(root)

    def append(self, event: AegisEvent) -> AegisEvent:
        path = self._path_for(event)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def list(
        self,
        limit: int = 100,
        type: str | None = None,
        mission_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
    ) -> list[AegisEvent]:
        events = [
            event
            for event in self._read_events()
            if self._matches(
                event,
                type=type,
                mission_id=mission_id,
                project_id=project_id,
                correlation_id=correlation_id,
            )
        ]
        events.sort(key=lambda item: item.timestamp, reverse=True)
        return events[: max(limit, 0)]

    def timeline(
        self,
        mission_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
    ) -> list[AegisEvent]:
        events = [
            event
            for event in self._read_events()
            if self._matches(
                event,
                mission_id=mission_id,
                project_id=project_id,
                correlation_id=correlation_id,
            )
        ]
        return sorted(events, key=lambda item: item.timestamp)

    def replay(
        self,
        correlation_id: str | None = None,
        mission_id: str | None = None,
    ) -> list[AegisEvent]:
        return self.timeline(mission_id=mission_id, correlation_id=correlation_id)

    def _path_for(self, event: AegisEvent) -> Path:
        return self.root / f"{event.timestamp.date().isoformat()}.jsonl"

    def _read_events(self) -> Iterable[AegisEvent]:
        if not self.root.exists():
            return []
        events: list[AegisEvent] = []
        for path in sorted(self.root.glob("*.jsonl")):
            events.extend(self._read_file(path))
        legacy = self.root / "events.json"
        if legacy.exists():
            events.extend(self._read_legacy_file(legacy))
        return events

    def _read_file(self, path: Path) -> list[AegisEvent]:
        events: list[AegisEvent] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return events
        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    events.append(AegisEvent.from_dict(data))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return events

    def _read_legacy_file(self, path: Path) -> list[AegisEvent]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        events = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                events.append(AegisEvent.from_dict(item))
            except (KeyError, TypeError, ValueError):
                continue
        return events

    def _matches(
        self,
        event: AegisEvent,
        *,
        type: str | None = None,
        mission_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        if type is not None and event.type != type:
            return False
        if mission_id is not None and event.mission_id != mission_id:
            return False
        if project_id is not None and event.project_id != project_id:
            return False
        if correlation_id is not None and event.correlation_id != correlation_id:
            return False
        return True
