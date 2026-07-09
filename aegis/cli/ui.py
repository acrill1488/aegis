import typer
from rich.console import Console
from rich.json import JSON

from aegis.ipc import IPCClient, IPCConnectionError
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()

DAEMON_NOT_RUNNING = "AEGIS daemon is not running. Start it with: aegis daemon serve"


@app.command("tree")
def tree():
    """Print the Unified UI Tree for the active browser page."""
    _print_result(_invoke("tree", {}))


@app.command("observe")
def observe():
    """Observe the active browser page as a compact Unified UI Model."""
    _print_result(_invoke("observe", {}))


@app.command("describe")
def describe():
    """Describe the compact UI observation for the active browser page."""
    _print_result(_invoke("describe", {}))


@app.command("locate")
def locate(query: str = typer.Argument(..., metavar="QUERY")):
    """Locate elements in the active browser page by visible UI text."""
    _print_result(_invoke("locate", {"query": query}))


def _invoke(action: str, payload: dict):
    try:
        output = IPCClient().request("ui", action, payload)
        return output if isinstance(output, dict) else {"result": output}
    except IPCConnectionError as exc:
        _print_error(str(exc))
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        _print_error(str(exc))
        raise typer.Exit(code=1) from exc


def _print_result(data: dict) -> None:
    console.print(JSON.from_data(to_plain(data)))


def _print_error(error: str) -> None:
    if "AEGIS daemon is not running" not in error and DAEMON_NOT_RUNNING in error:
        error = DAEMON_NOT_RUNNING
    console.print(f"[red]{error}[/red]")
