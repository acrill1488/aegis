from aegis.live.watchers.workspace import WorkspaceWatcher


class FakeEvents:
    def __init__(self):
        self.published = []

    def publish(self, event_type, source, payload):
        self.published.append(
            {"event_type": event_type, "source": source, "payload": payload}
        )


class FakeLiveContext:
    def __init__(self):
        self.entries = []

    def set(self, **kwargs):
        self.entries.append(kwargs)


class FakeCore:
    def __init__(self):
        self.events = FakeEvents()
        self.live_context = FakeLiveContext()


class FakeEvent:
    def __init__(self, src_path, is_directory, event_type):
        self.src_path = src_path
        self.is_directory = is_directory
        self.event_type = event_type


def test_workspace_watcher_publishes_file_event_and_updates_context(tmp_path):
    core = FakeCore()
    watcher = WorkspaceWatcher(core, path=str(tmp_path))
    file_path = tmp_path / "note.txt"

    watcher.handle_event(FakeEvent(file_path, is_directory=False, event_type="created"))

    payload = {
        "path": str(file_path),
        "is_directory": False,
        "event": "workspace.file_created",
    }
    assert core.events.published == [
        {
            "event_type": "workspace.file_created",
            "source": "workspace_watcher",
            "payload": payload,
        }
    ]
    assert core.live_context.entries[0] == {
        "key": "workspace.last_event",
        "value": payload,
        "source": "workspace_watcher",
        "ttl_seconds": 3600,
    }
    assert core.live_context.entries[1] == {
        "key": "workspace.root",
        "value": {"path": str(tmp_path)},
        "source": "workspace_watcher",
    }


def test_workspace_watcher_ignores_directory_modified(tmp_path):
    core = FakeCore()
    watcher = WorkspaceWatcher(core, path=str(tmp_path))

    watcher.handle_event(FakeEvent(tmp_path, is_directory=True, event_type="modified"))

    assert core.events.published == []
    assert core.live_context.entries == []


def test_workspace_watcher_ignores_service_directories(tmp_path):
    core = FakeCore()
    watcher = WorkspaceWatcher(core, path=str(tmp_path))

    for dirname in ("live", "events", "cache", "logs", ".git", "__pycache__"):
        watcher.handle_event(
            FakeEvent(
                tmp_path / dirname / "internal.json",
                is_directory=False,
                event_type="modified",
            )
        )

    assert core.events.published == []
    assert core.live_context.entries == []


def test_workspace_watcher_ignores_moves_to_service_directories(tmp_path):
    core = FakeCore()
    watcher = WorkspaceWatcher(core, path=str(tmp_path))
    event = FakeEvent(tmp_path / "note.txt", is_directory=False, event_type="moved")
    event.dest_path = tmp_path / "events" / "note.txt"

    watcher.handle_event(event)

    assert core.events.published == []
    assert core.live_context.entries == []


def test_workspace_watcher_status_includes_ignore_dirs(tmp_path):
    core = FakeCore()
    watcher = WorkspaceWatcher(core, path=str(tmp_path))

    status = watcher.status()

    assert status["ignore_dirs"] == [
        "live",
        "events",
        "cache",
        "logs",
        ".git",
        "__pycache__",
    ]


def test_workspace_watcher_publishes_moved_event_and_notifies(tmp_path):
    core = FakeCore()
    messages = []
    watcher = WorkspaceWatcher(
        core,
        path=str(tmp_path),
        on_event=lambda message, payload: messages.append((message, payload)),
    )
    event = FakeEvent(tmp_path / "old.txt", is_directory=False, event_type="moved")
    event.dest_path = tmp_path / "new.txt"

    watcher.handle_event(event)

    payload = {
        "path": str(tmp_path / "old.txt"),
        "is_directory": False,
        "event": "workspace.file_moved",
        "dest_path": str(tmp_path / "new.txt"),
    }
    assert core.events.published == [
        {
            "event_type": "workspace.file_moved",
            "source": "workspace_watcher",
            "payload": payload,
        }
    ]
    assert core.live_context.entries[0]["key"] == "workspace.last_event"
    assert messages == [
        (
            f"workspace.file_moved {tmp_path / 'old.txt'} -> {tmp_path / 'new.txt'}",
            payload,
        )
    ]
