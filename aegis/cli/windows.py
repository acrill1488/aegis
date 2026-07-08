import time

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from aegis.agents.runtime import AgentInvocation
from aegis.agents.windows import ProcessWatcher
from aegis.core.core import AegisCore
from aegis.serialization import to_plain

WINDOWS_AGENT_ID = "windows-agent"

app = typer.Typer()
console = Console()


@app.command("status")
def status():
    """Show Windows system status through WindowsAgent."""
    result = _invoke("windows.system.status")
    _print_json(result.output)


@app.command("processes")
def processes():
    """List Windows processes through WindowsAgent."""
    result = _invoke("windows.process.list")
    table = Table(title="Windows Processes")
    table.add_column("PID", justify="right")
    table.add_column("Name")
    table.add_column("User")
    table.add_column("CPU", justify="right")
    table.add_column("Memory", justify="right")

    for process in result.output.get("processes", []):
        table.add_row(
            str(process["pid"]),
            process["name"],
            process.get("username") or "-",
            f"{process['cpu_percent']:.1f}%",
            f"{process['memory_mb']:.2f} MB",
        )
    console.print(table)


@app.command("context")
def context():
    """Show live context entries through WindowsAgent."""
    result = _invoke("windows.context.snapshot")
    _print_json(result.output)


@app.command("watch-processes")
def watch_processes(
    interval_seconds: float = typer.Option(5.0, "--interval-seconds", "--interval"),
):
    """Watch process start/stop events in the foreground."""
    core = AegisCore()
    _require_windows_agent(core)
    watcher = ProcessWatcher(core, interval_seconds=interval_seconds, on_event=_print_event)

    try:
        watcher.start()
    except RuntimeError as exc:
        console.print(f"[red]Cannot start process watcher:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print("Watching Windows processes")
    console.print("Press Ctrl+C to stop")
    core.scheduler.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("[yellow]Stopping process watcher...[/yellow]")
    finally:
        watcher.stop()
        core.scheduler.stop()


def _invoke(capability_id: str):
    core = AegisCore()
    _require_windows_agent(core)
    result = core.agent_runtime.invoke(
        WINDOWS_AGENT_ID,
        AgentInvocation(capability_id=capability_id),
    )
    if not result.success:
        console.print(f"[red]{result.error or 'WindowsAgent invocation failed'}[/red]")
        raise typer.Exit(code=1)
    return result


def _require_windows_agent(core: AegisCore) -> None:
    if core.agent_runtime.registry.get(WINDOWS_AGENT_ID) is None:
        console.print("[red]WindowsAgent is only available on Windows.[/red]")
        raise typer.Exit(code=1)


def _print_event(event_type: str, payload: dict) -> None:
    console.print(f"{event_type} pid={payload['pid']} name={payload['name']}")


def _print_json(data: dict | list) -> None:
    console.print(JSON.from_data(to_plain(data)))
