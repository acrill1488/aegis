import logging
import threading

from aegis.agents.windows import process_watcher
from aegis.agents.windows.process_watcher import ProcessWatcher
from aegis.agents.windows import system_watcher
from aegis.agents.windows.system_watcher import SystemWatcher
from aegis.agents.windows import window_watcher
from aegis.agents.windows.window_watcher import WindowWatcher
from aegis.core.core import AegisCore
from aegis.runtime.scheduler import Scheduler


def test_scheduler_runs_named_periodic_task():
    scheduler = Scheduler(tick_seconds=0.005)
    called = threading.Event()

    scheduler.register_periodic(
        "test.task",
        called.set,
        interval_seconds=0.01,
        run_immediately=True,
    )

    try:
        scheduler.start()
        assert called.wait(timeout=1.0)
        status = scheduler.status()
        assert status["running"] is True
        assert status["task_count"] == 1
        assert status["tasks"][0]["name"] == "test.task"
    finally:
        scheduler.stop()


def test_scheduler_logs_task_errors_and_keeps_running(caplog):
    scheduler = Scheduler(tick_seconds=0.005)
    recovered = threading.Event()
    calls = {"count": 0}

    def flaky_task():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary failure")
        recovered.set()

    scheduler.register_periodic(
        "test.flaky",
        flaky_task,
        interval_seconds=0.01,
        run_immediately=True,
    )

    try:
        with caplog.at_level(logging.ERROR):
            scheduler.start()
            assert recovered.wait(timeout=1.0)
    finally:
        scheduler.stop()

    task = scheduler.registry.get("test.flaky")
    assert task is not None
    assert task.error_count == 1
    assert calls["count"] >= 2
    assert "Scheduled task failed: test.flaky" in caplog.text


def test_core_exposes_scheduler_service():
    core = AegisCore()

    try:
        assert core.registry.get("scheduler") is core.scheduler
        assert core.scheduler.status()["scheduler"] == "runtime"
    finally:
        core.scheduler.stop()


def test_process_watcher_uses_core_scheduler(monkeypatch):
    core = _FakeCore()
    watcher = ProcessWatcher(core, interval_seconds=0.05)

    monkeypatch.setattr(process_watcher, "psutil", _FakePsutil)

    try:
        status = watcher.start()
        assert status["running"] is True
        assert status["thread_alive"] is False
        assert core.scheduler.registry.get("process-watcher") is not None

        core.scheduler.start()
        assert watcher.status()["thread_alive"] is True

        watcher.stop()

        assert watcher.status()["running"] is False
        assert core.scheduler.registry.get("process-watcher") is None
    finally:
        core.scheduler.stop()


def test_system_watcher_uses_scheduler_and_updates_context(monkeypatch):
    core = _FakeCore()
    watcher = SystemWatcher(
        core,
        interval_seconds=0.05,
        cpu_high_percent=90.0,
        memory_high_percent=90.0,
        disk_low_free_percent=10.0,
        disk_low_free_gb=5.0,
    )

    monkeypatch.setattr(system_watcher, "psutil", _FakeSystemPsutil)
    monkeypatch.setattr(watcher, "_check_internet", lambda: True)

    try:
        status = watcher.start()
        assert status["running"] is True
        assert status["thread_alive"] is False
        assert core.scheduler.registry.get("system-watcher") is not None

        keys = {entry["key"] for entry in core.live_context.entries}
        assert {
            "system.cpu",
            "system.memory",
            "system.disk",
            "system.network",
            "system.internet",
        }.issubset(keys)
        assert core.events.published[0][0] == "system.cpu_high"
        assert core.events.published[1][0] == "system.memory_high"
        assert core.events.published[2][0] == "system.disk_low"

        core.scheduler.start()
        assert watcher.status()["thread_alive"] is True

        watcher.stop()

        assert watcher.status()["running"] is False
        assert core.scheduler.registry.get("system-watcher") is None
    finally:
        core.scheduler.stop()


def test_system_watcher_publishes_internet_transitions(monkeypatch):
    core = _FakeCore()
    watcher = SystemWatcher(core)
    states = iter([True, False, True])

    monkeypatch.setattr(system_watcher, "psutil", _FakeSystemPsutil)
    monkeypatch.setattr(watcher, "_check_internet", lambda: next(states))

    watcher.tick()
    watcher.tick()
    watcher.tick()

    event_types = [event_type for event_type, _source, _payload in core.events.published]
    assert "system.internet_lost" in event_types
    assert "system.internet_restored" in event_types


def test_window_watcher_uses_scheduler_and_updates_context(monkeypatch):
    core = _FakeCore()
    watcher = WindowWatcher(core, interval_seconds=0.05)

    monkeypatch.setattr(window_watcher, "win32gui", _FakeWin32Gui)
    monkeypatch.setattr(window_watcher, "win32process", _FakeWin32Process)
    monkeypatch.setattr(window_watcher, "psutil", _FakeWindowPsutil)

    try:
        status = watcher.start()
        assert status["running"] is True
        assert status["thread_alive"] is False
        assert core.scheduler.registry.get("window-watcher") is not None

        keys = {entry["key"] for entry in core.live_context.entries}
        assert {
            "windows.active_window",
            "windows.active_process",
            "windows.active_pid",
            "windows.last_window_event",
        }.issubset(keys)
        assert core.events.published[0][0] == "window.focused"

        core.scheduler.start()
        assert watcher.status()["thread_alive"] is True

        watcher.stop()

        assert watcher.status()["running"] is False
        assert core.scheduler.registry.get("window-watcher") is None
    finally:
        core.scheduler.stop()


def test_window_watcher_publishes_changed_when_focus_changes(monkeypatch):
    core = _FakeCore()
    watcher = WindowWatcher(core)
    gui = _ChangingWin32Gui()

    monkeypatch.setattr(window_watcher, "win32gui", gui)
    monkeypatch.setattr(window_watcher, "win32process", _FakeWin32Process)
    monkeypatch.setattr(window_watcher, "psutil", _FakeWindowPsutil)

    watcher.tick()
    watcher.tick()

    event_types = [event_type for event_type, _source, _payload in core.events.published]
    assert event_types == ["window.focused", "window.changed", "window.focused"]


class _FakeCore:
    def __init__(self):
        self.scheduler = Scheduler(tick_seconds=0.005)
        self.events = _FakeEvents()
        self.live_context = _FakeLiveContext()


class _FakeEvents:
    def __init__(self):
        self.published = []

    def publish(self, *args, **kwargs):
        self.published.append((args[0], kwargs["source"], kwargs["payload"]))
        return None


class _FakeLiveContext:
    def __init__(self):
        self.entries = []

    def set(self, *args, **kwargs):
        self.entries.append(kwargs)
        return None


class _FakeProcess:
    info = {"pid": 1, "name": "example.exe", "username": "user"}


class _FakePsutil:
    NoSuchProcess = RuntimeError
    AccessDenied = PermissionError
    ZombieProcess = RuntimeError

    @staticmethod
    def process_iter(attrs):
        return [_FakeProcess()]


class _FakeMemory:
    total = 16 * 1024**3
    used = 15 * 1024**3
    available = 1 * 1024**3
    percent = 93.75


class _FakeDiskUsage:
    total = 100 * 1024**3
    used = 96 * 1024**3
    free = 4 * 1024**3
    percent = 96.0


class _FakePartition:
    mountpoint = "C:\\"


class _FakeCounters:
    bytes_sent = 100
    bytes_recv = 200
    packets_sent = 3
    packets_recv = 4


class _FakeAddress:
    family = system_watcher.socket.AF_INET
    address = "192.168.1.10"


class _FakeSystemPsutil:
    @staticmethod
    def cpu_percent(interval=None):
        return 95.0

    @staticmethod
    def cpu_count(logical=True):
        return 8 if logical else 4

    @staticmethod
    def virtual_memory():
        return _FakeMemory()

    @staticmethod
    def disk_partitions(all=False):
        return [_FakePartition()]

    @staticmethod
    def disk_usage(path):
        return _FakeDiskUsage()

    @staticmethod
    def net_io_counters():
        return _FakeCounters()

    @staticmethod
    def net_if_addrs():
        return {"eth0": [_FakeAddress()]}


class _FakeWin32Gui:
    @staticmethod
    def GetForegroundWindow():
        return 100

    @staticmethod
    def GetWindowText(hwnd):
        return "Example Window"


class _ChangingWin32Gui:
    def __init__(self):
        self._hwnds = iter([100, 200])

    def GetForegroundWindow(self):
        return next(self._hwnds)

    def GetWindowText(self, hwnd):
        return f"Example Window {hwnd}"


class _FakeWin32Process:
    @staticmethod
    def GetWindowThreadProcessId(hwnd):
        return (1, hwnd + 1000)


class _FakePsutilProcess:
    def __init__(self, pid):
        self.pid = pid

    def name(self):
        return f"example-{self.pid}.exe"


class _FakeWindowPsutil:
    NoSuchProcess = RuntimeError
    AccessDenied = PermissionError
    ZombieProcess = RuntimeError
    Process = _FakePsutilProcess
