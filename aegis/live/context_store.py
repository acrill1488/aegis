import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import ContextEntry, ContextSnapshot


DEFAULT_CONTEXT_PATH = Path(r"F:\AI_WORKSPACE\live\context.json")


class ContextStore:
    """Current-state context store for AEGIS Live Context v1."""

    def __init__(self, path: str | Path = DEFAULT_CONTEXT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, ContextEntry] = {}
        self._load()

    def set(
        self,
        key: str,
        value: dict,
        source: str,
        ttl_seconds: int | None = None,
        metadata: dict | None = None,
    ) -> ContextEntry:
        entry = ContextEntry(
            key=key,
            value=value,
            source=source,
            updated_at=datetime.now(),
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )
        self._entries[key] = entry
        self._save()
        return entry

    def get(self, key: str) -> ContextEntry | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            return None
        return entry

    def list(self, prefix: str | None = None) -> list[ContextEntry]:
        entries = [entry for entry in self._entries.values() if not self._is_expired(entry)]
        if prefix is not None:
            entries = [entry for entry in entries if entry.key.startswith(prefix)]
        return sorted(entries, key=lambda entry: entry.key)

    def snapshot(self, prefix: str | None = None) -> ContextSnapshot:
        return ContextSnapshot(
            entries=self.list(prefix=prefix),
            created_at=datetime.now(),
            metadata={"prefix": prefix},
        )

    def delete(self, key: str) -> bool:
        if key not in self._entries:
            return False
        del self._entries[key]
        self._save()
        return True

    def prune_expired(self) -> int:
        expired_keys = [
            key for key, entry in self._entries.items() if self._is_expired(entry)
        ]
        for key in expired_keys:
            del self._entries[key]
        if expired_keys:
            self._save()
        return len(expired_keys)

    def _is_expired(self, entry: ContextEntry) -> bool:
        if entry.ttl_seconds is None:
            return False
        expires_at = entry.updated_at + timedelta(seconds=entry.ttl_seconds)
        return datetime.now() >= expires_at

    def _load(self) -> None:
        if not self.path.exists():
            self._save()
            return

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            self._entries = {}
            return

        entries: dict[str, ContextEntry] = {}
        for item in data.get("entries", []):
            try:
                entry = self._entry_from_dict(item)
            except (KeyError, TypeError, ValueError):
                continue
            entries[entry.key] = entry
        self._entries = entries

    def _save(self) -> None:
        data = {
            "entries": [self._entry_to_dict(entry) for entry in self._entries.values()],
            "updated_at": datetime.now().isoformat(),
        }
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _entry_from_dict(self, item: dict) -> ContextEntry:
        value = item["value"]
        metadata = item.get("metadata", {})
        if not isinstance(value, dict):
            raise ValueError("Context entry value must be a JSON object.")
        if not isinstance(metadata, dict):
            raise ValueError("Context entry metadata must be a JSON object.")

        return ContextEntry(
            key=item["key"],
            value=value,
            source=item["source"],
            updated_at=datetime.fromisoformat(item["updated_at"]),
            ttl_seconds=item.get("ttl_seconds"),
            metadata=metadata,
        )

    def _entry_to_dict(self, entry: ContextEntry) -> dict:
        return {
            "key": entry.key,
            "value": entry.value,
            "source": entry.source,
            "updated_at": entry.updated_at.isoformat(),
            "ttl_seconds": entry.ttl_seconds,
            "metadata": entry.metadata,
        }
