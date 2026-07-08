import logging
import threading

from aegis.agents.windows import process_watcher
from aegis.agents.windows.process_watcher import ProcessWatcher
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


class _FakeCore:
    def __init__(self):
        self.scheduler = Scheduler(tick_seconds=0.005)
        self.events = _FakeEvents()
        self.live_context = _FakeLiveContext()


class _FakeEvents:
    def publish(self, *args, **kwargs):
        return None


class _FakeLiveContext:
    def set(self, *args, **kwargs):
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
