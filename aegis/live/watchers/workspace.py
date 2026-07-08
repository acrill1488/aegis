import logging
from pathlib import Path
from typing import Any, Callable

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    FileSystemEvent = Any
    FileSystemEventHandler = object
    Observer = None


_EVENT_TYPES = {
    (False, "created"): "workspace.file_created",
    (False, "modified"): "workspace.file_modified",
    (False, "deleted"): "workspace.file_deleted",
    (True, "created"): "workspace.directory_created",
    (True, "deleted"): "workspace.directory_deleted",
}
_MOVED_EVENT_TYPE = "workspace.file_moved"
_LOGGER = logging.getLogger(__name__)
DEFAULT_IGNORE_DIRS = ("live", "events", "cache", "logs", ".git", "__pycache__")


class _WorkspaceEventHandler(FileSystemEventHandler):
    def __init__(self, watcher: "WorkspaceWatcher"):
        super().__init__()
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        self._watcher.handle_event(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._watcher.handle_event(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._watcher.handle_event(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._watcher.handle_event(event)


class WorkspaceWatcher:
    """Watch workspace file changes and mirror them into AEGIS Live Context."""

    source = "workspace_watcher"

    def __init__(
        self,
        core,
        path: str,
        on_event: Callable[[str, dict], None] | None = None,
        ignore_dirs: tuple[str, ...] | None = None,
    ):
        self.core = core
        self.root_path = Path(path).resolve()
        self.path = str(self.root_path)
        self.recursive = True
        self.on_event = on_event
        self.ignore_dirs = tuple(ignore_dirs or DEFAULT_IGNORE_DIRS)
        self._ignore_dir_names = {dirname.lower() for dirname in self.ignore_dirs}
        self._observer = None
        self._handler = _WorkspaceEventHandler(self)
        self._running = False
        self._last_event: dict | None = None
        self._error: str | None = None

    def start(self) -> dict:
        if Observer is None:
            raise RuntimeError("watchdog is required for WorkspaceWatcher.")
        if self._running:
            return self.status()

        watched_path = Path(self.path)
        if not watched_path.exists():
            raise FileNotFoundError(f"Workspace path does not exist: {watched_path}")
        if not watched_path.is_dir():
            raise NotADirectoryError(f"Workspace path is not a directory: {watched_path}")

        self._set_workspace_root()
        self._observer = Observer()
        self._observer.schedule(self._handler, self.path, recursive=self.recursive)
        self._observer.start()
        self._running = True
        self._error = None
        return self.status()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._running = False

    def status(self) -> dict:
        observer_alive = bool(
            self._observer is not None and self._observer.is_alive()
        )
        return {
            "watcher": "workspace",
            "path": self.path,
            "running": self._running,
            "recursive": self.recursive,
            "ignore_dirs": list(self.ignore_dirs),
            "observer_alive": observer_alive,
            "last_event": self._last_event,
            "error": self._error,
        }

    def handle_event(self, event: FileSystemEvent) -> None:
        payload = self._payload_for_event(event)
        if payload is None:
            return
        event_name = payload["event"]

        try:
            self.core.events.publish(
                event_name,
                source=self.source,
                payload=payload,
            )
            self.core.live_context.set(
                key="workspace.last_event",
                value=payload,
                source=self.source,
                ttl_seconds=3600,
            )
            self._set_workspace_root()
            self._last_event = payload
            self._error = None
            self._notify(event_name, payload)
        except Exception as exc:  # pragma: no cover - defensive boundary
            self._error = str(exc)
            raise

    def _payload_for_event(self, event: FileSystemEvent) -> dict | None:
        src_path = Path(event.src_path)
        dest_path = getattr(event, "dest_path", None)
        if self._is_ignored(src_path) or (
            dest_path is not None and self._is_ignored(Path(dest_path))
        ):
            return None

        if event.event_type == "moved":
            payload = {
                "path": str(src_path),
                "is_directory": bool(event.is_directory),
                "event": _MOVED_EVENT_TYPE,
            }
            if dest_path is not None:
                payload["dest_path"] = str(Path(dest_path))
            return payload

        event_name = _EVENT_TYPES.get((bool(event.is_directory), event.event_type))
        if event_name is None:
            return None

        return {
            "path": str(src_path),
            "is_directory": bool(event.is_directory),
            "event": event_name,
        }

    def _is_ignored(self, path: Path) -> bool:
        try:
            relative_parts = path.resolve().relative_to(self.root_path).parts
        except ValueError:
            return False
        return any(part.lower() in self._ignore_dir_names for part in relative_parts)

    def _notify(self, event_name: str, payload: dict) -> None:
        if event_name == _MOVED_EVENT_TYPE:
            message = (
                f"{event_name} {payload['path']} -> "
                f"{payload.get('dest_path', '')}".rstrip()
            )
        else:
            message = f"{event_name} {payload['path']}"

        _LOGGER.info(message)
        if self.on_event is not None:
            self.on_event(message, payload)

    def _set_workspace_root(self) -> None:
        self.core.live_context.set(
            key="workspace.root",
            value={"path": self.path},
            source=self.source,
        )
