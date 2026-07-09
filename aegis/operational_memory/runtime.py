from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import EXPERIENCE_TYPES, OperationalExperience
from .store import OperationalMemoryStore


DEFAULT_OPERATIONAL_MEMORY_PATH = Path("F:/AI_WORKSPACE/memory/operational_memory.json")


class OperationalMemoryRuntime:
    """Runtime-facing memory for mission, skill, recovery, and UI experience."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        store_path: Path | str = DEFAULT_OPERATIONAL_MEMORY_PATH,
        store: OperationalMemoryStore | None = None,
    ):
        self.core = core
        self.store = store or OperationalMemoryStore(store_path)
        self._experiences = self.store.load()
        self._index: dict[str, dict[str, list[OperationalExperience]]] = {}
        self._rebuild_index()

    def record(
        self,
        experience: OperationalExperience | dict[str, Any],
    ) -> OperationalExperience:
        if isinstance(experience, OperationalExperience):
            record = experience
        else:
            record = OperationalExperience.from_dict(experience)
        if record.type not in EXPERIENCE_TYPES:
            raise ValueError(f"Unsupported operational experience type: {record.type}")
        record.data = dict(to_plain(record.data) or {})
        record.metadata = dict(to_plain(record.metadata) or {})
        self._experiences.append(record)
        self.store.save(self._experiences)
        self._add_to_index(record)
        self._publish_recorded(record)
        return record

    def list(
        self,
        type: str | None = None,
        source: str | None = None,
        limit: int = 50,
    ) -> list[OperationalExperience]:
        records = self._filter(type=type, source=source)
        records = sorted(records, key=lambda item: item.created_at, reverse=True)
        return records[: max(limit, 0)]

    def search(
        self,
        query: str,
        type: str | None = None,
        source: str | None = None,
        limit: int = 20,
    ) -> list[OperationalExperience]:
        needle = query.casefold()
        matches = []
        for record in self._filter(type=type, source=source):
            haystack = " ".join(
                [
                    record.type,
                    record.source,
                    record.summary,
                    str(to_plain(record.data)),
                    str(to_plain(record.metadata)),
                ]
            ).casefold()
            if needle in haystack:
                matches.append(record)
        matches = sorted(matches, key=lambda item: item.created_at, reverse=True)
        return matches[: max(limit, 0)]

    def stats(self) -> dict[str, Any]:
        by_type: dict[str, int] = defaultdict(int)
        by_source: dict[str, int] = defaultdict(int)
        for record in self._experiences:
            by_type[record.type] += 1
            by_source[record.source] += 1
        latest = max(self._experiences, key=lambda item: item.created_at, default=None)
        return {
            "path": str(self.store.path),
            "total": len(self._experiences),
            "by_type": dict(sorted(by_type.items())),
            "by_source": dict(sorted(by_source.items())),
            "latest": to_plain(latest),
        }

    def clear(self, type: str | None = None) -> int:
        if type is None:
            removed = len(self._experiences)
            self._experiences = []
        else:
            before = len(self._experiences)
            self._experiences = [
                record for record in self._experiences if record.type != type
            ]
            removed = before - len(self._experiences)
        self.store.replace(self._experiences)
        self._rebuild_index()
        return removed

    def suggest_selector(
        self,
        action: str,
        query: str,
        role: str | None = None,
        source: str | None = None,
    ) -> str | None:
        records = self.list(
            type="recovery.selector_patch",
            source=source,
            limit=len(self._experiences),
        )
        for record in records:
            data = record.data
            if data.get("query") != query:
                continue
            if data.get("action", record.source) != action and record.source != action:
                continue
            if role is not None and data.get("role") != role:
                continue
            selector = data.get("new_selector")
            if isinstance(selector, str) and selector.strip():
                return selector
        return None

    def _filter(
        self,
        *,
        type: str | None = None,
        source: str | None = None,
    ) -> list[OperationalExperience]:
        if type is None and source is None:
            return list(self._experiences)
        if type is not None and source is not None:
            return list(self._index.get(type, {}).get(source, []))
        if type is not None:
            records: list[OperationalExperience] = []
            for items in self._index.get(type, {}).values():
                records.extend(items)
            return records
        return [record for record in self._experiences if record.source == source]

    def _rebuild_index(self) -> None:
        self._index = {}
        for record in self._experiences:
            self._add_to_index(record)

    def _add_to_index(self, record: OperationalExperience) -> None:
        self._index.setdefault(record.type, {}).setdefault(record.source, []).append(record)

    def _publish_recorded(self, record: OperationalExperience) -> None:
        event_platform = getattr(self.core, "event_platform", None)
        publish = getattr(event_platform, "publish", None)
        if not callable(publish):
            return
        metadata = dict(record.metadata or {})
        data = dict(record.data or {})
        try:
            publish(
                "memory.recorded",
                "operational_memory",
                {
                    "experience_id": record.id,
                    "type": record.type,
                    "source": record.source,
                    "summary": record.summary,
                },
                project_id=metadata.get("project_id") or data.get("project_id"),
                mission_id=metadata.get("mission_id") or data.get("mission_id"),
                skill_id=metadata.get("skill_id") or data.get("skill_id"),
                correlation_id=metadata.get("correlation_id") or data.get("correlation_id"),
            )
        except Exception:
            return
