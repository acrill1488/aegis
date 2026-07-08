from __future__ import annotations

from threading import RLock

from .base import BaseWatcher


class WatcherRegistry:
    """Thread-safe registry for Scheduler-managed watchers."""

    def __init__(self) -> None:
        self._watchers: dict[str, BaseWatcher] = {}
        self._lock = RLock()

    def register(
        self,
        watcher: BaseWatcher,
        *,
        replace: bool = False,
    ) -> BaseWatcher:
        with self._lock:
            if watcher.id in self._watchers and not replace:
                raise ValueError(f"Watcher already registered: {watcher.id}")
            self._watchers[watcher.id] = watcher
            return watcher

    def unregister(self, watcher_id: str) -> BaseWatcher | None:
        with self._lock:
            return self._watchers.pop(watcher_id, None)

    def get(self, watcher_id: str) -> BaseWatcher | None:
        with self._lock:
            return self._watchers.get(watcher_id)

    def list(self) -> list[BaseWatcher]:
        with self._lock:
            return list(self._watchers.values())

    def enabled(self) -> list[BaseWatcher]:
        with self._lock:
            return [watcher for watcher in self._watchers.values() if watcher.enabled]
