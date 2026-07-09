from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("windows")
def windows():
    """List desktop windows."""
    _print_json(_runtime().windows())


@app.command("active")
def active():
    """Show the active desktop window."""
    _print_json(_runtime().active())


@app.command("activate")
def activate(window_id: str = typer.Argument(..., metavar="WINDOW_ID")):
    """Activate a desktop window."""
    _print_json(_runtime().activate(window_id))


@app.command("close")
def close(window_id: str = typer.Argument(..., metavar="WINDOW_ID")):
    """Close a desktop window."""
    _print_json(_runtime().close(window_id))


@app.command("launch")
def launch(command: str = typer.Argument(..., metavar="COMMAND")):
    """Launch a desktop app."""
    _print_json(_runtime().launch(command))


@app.command("processes")
def processes(limit: int = typer.Option(100, "--limit", "-l")):
    """List desktop processes."""
    _print_json(_runtime().processes({"limit": limit}))


@app.command("screenshot")
def screenshot(path: Path | None = typer.Argument(None, metavar="PATH")):
    """Create a desktop screenshot."""
    payload = {"path": str(path)} if path is not None else {}
    _print_json(_runtime().screenshot(payload))


def _runtime():
    return AegisCore().desktop_runtime


def _print_json(data: dict | list) -> None:
    console.print(JSON.from_data(to_plain(data)))
