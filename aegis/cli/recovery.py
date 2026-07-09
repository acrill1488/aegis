from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from aegis.recovery_engine import RecoveryEngineRuntime
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("status")
def status():
    """Show Recovery Engine status."""
    runtime = RecoveryEngineRuntime()
    console.print(JSON.from_data(to_plain(runtime.status())))


@app.command("history")
def history():
    """Show Recovery Engine attempt history."""
    runtime = RecoveryEngineRuntime()
    rows = runtime.history()
    table = Table(title="Recovery History")
    table.add_column("Started")
    table.add_column("Source")
    table.add_column("Strategy")
    table.add_column("Retry")
    table.add_column("Reason")
    for item in rows:
        metadata = item.get("metadata") or {}
        table.add_row(
            str(item.get("started_at") or ""),
            str(item.get("source") or ""),
            str(item.get("strategy") or ""),
            "yes" if item.get("success") else "no",
            str(metadata.get("reason") or ""),
        )
    console.print(table)
