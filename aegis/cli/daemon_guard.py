from __future__ import annotations

import typer
from rich.console import Console

from aegis.daemon import DaemonSupervisor
from aegis.daemon.state import STATE_READY


def ensure_daemon_running(console: Console) -> dict:
    result = DaemonSupervisor().ensure_running()
    status = result.get("status") if isinstance(result.get("status"), dict) else result
    if result.get("running") and status.get("state") == STATE_READY:
        return result

    log_file = result.get("log_file") or "F:/AI_WORKSPACE/daemon/daemon.log"
    state = result.get("state") or status.get("state")
    error = result.get("error") or f"AEGIS daemon is not READY (state: {state})."
    console.print(f"[red]{error}[/red]")
    console.print(f"[yellow]Daemon log:[/yellow] {log_file}")
    raise typer.Exit(code=1)
