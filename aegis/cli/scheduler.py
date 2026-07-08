import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from aegis.agents.windows import ProcessWatcher
from aegis.core.core import AegisCore
from aegis.serialization import to_plain


app = typer.Typer()
console = Console()


@app.command("status")
def status():
    """Show Scheduler status."""
    core = AegisCore()
    try:
        _register_default_tasks(core)
        console.print(JSON.from_data(to_plain(core.scheduler.status())))
    finally:
        core.scheduler.stop()


@app.command("tasks")
def tasks():
    """List registered Scheduler tasks."""
    core = AegisCore()
    try:
        _register_default_tasks(core)
        task_statuses = core.scheduler.status()["tasks"]
        table = Table(title="Scheduler Tasks")
        table.add_column("Name")
        table.add_column("Enabled")
        table.add_column("Interval", justify="right")
        table.add_column("Runs", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Next Run", justify="right")
        table.add_column("Last Error")

        for task in task_statuses:
            table.add_row(
                task["name"],
                "yes" if task["enabled"] else "no",
                f"{task['interval_seconds']:.2f}s",
                str(task["run_count"]),
                str(task["error_count"]),
                f"{task['next_run_in_seconds']:.2f}s",
                task["last_error"] or "-",
            )

        console.print(table)
    finally:
        core.scheduler.stop()


@app.command("run-once")
def run_once(task_name: str = typer.Argument(..., metavar="TASK_NAME")):
    """Run a registered Scheduler task once."""
    core = AegisCore()
    try:
        _register_default_tasks(core)
        result = core.scheduler.run_once(task_name)
    except KeyError as exc:
        console.print(f"[red]Unknown scheduler task:[/red] {task_name}")
        raise typer.Exit(code=1) from exc
    finally:
        core.scheduler.stop()

    console.print(JSON.from_data(to_plain(result.status())))


def _register_default_tasks(core: AegisCore) -> None:
    if core.scheduler.registry.get("process-watcher") is not None:
        return
    ProcessWatcher(core).start()
