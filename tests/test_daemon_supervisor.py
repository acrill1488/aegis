from __future__ import annotations

from pathlib import Path

from aegis.daemon.state import STATE_DEAD, STATE_READY, STATE_STALE, STATE_STARTING
from aegis.daemon.supervisor import DaemonSupervisor


def test_status_returns_dead_without_ipc_or_pid(tmp_path: Path, monkeypatch) -> None:
    supervisor = DaemonSupervisor(daemon_dir=tmp_path)
    monkeypatch.setattr(supervisor, "_ipc_status", lambda: None)

    status = supervisor.status()

    assert status["state"] == STATE_DEAD
    assert status["running"] is False


def test_status_reports_stale_pid_and_removes_pid_file(tmp_path: Path, monkeypatch) -> None:
    supervisor = DaemonSupervisor(daemon_dir=tmp_path)
    supervisor.pid_path.write_text("424242", encoding="utf-8")

    monkeypatch.setattr(supervisor, "_ipc_status", lambda: None)
    monkeypatch.setattr(supervisor, "_pid_exists", lambda pid: False)

    status = supervisor.status()

    assert status["state"] == STATE_STALE
    assert status["running"] is False
    assert status["stale_pid"] == 424242
    assert not supervisor.pid_path.exists()


def test_status_reports_starting_for_live_process_without_ready_ipc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    supervisor = DaemonSupervisor(daemon_dir=tmp_path)
    supervisor.pid_path.write_text("424242", encoding="utf-8")

    monkeypatch.setattr(supervisor, "_ipc_status", lambda: None)
    monkeypatch.setattr(supervisor, "_pid_exists", lambda pid: True)
    monkeypatch.setattr(supervisor, "_process_matches_daemon", lambda pid: True)

    status = supervisor.status()

    assert status["state"] == STATE_STARTING
    assert status["running"] is False


def test_ensure_running_reuses_existing_daemon(tmp_path: Path, monkeypatch) -> None:
    supervisor = DaemonSupervisor(daemon_dir=tmp_path)
    health = {"status": "ok", "version": "test"}

    monkeypatch.setattr(supervisor, "_ipc_status", lambda: health)

    result = supervisor.ensure_running()

    assert result["running"] is True
    assert result["started"] is False
    assert result["status"]["state"] == STATE_READY
    assert result["status"]["ipc"] == health


def test_start_command_uses_project_entrypoint(tmp_path: Path) -> None:
    supervisor = DaemonSupervisor(
        daemon_dir=tmp_path,
        python_executable="python",
    )

    assert supervisor._command() == [
        "python",
        "-m",
        "aegis.cli.main",
        "daemon",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "8787",
    ]
