"""GreenBoost system resource commands."""

import json

import typer
from rich.console import Console

from .client import GreenBoostClient
from .errors import GreenBoostError
from .runtime import GreenBoostRuntime

app = typer.Typer()
console = Console()


def _print(operation: str) -> None:
    try:
        with GreenBoostClient() as client:
            value = getattr(client, operation)()
        if isinstance(value, tuple):
            payload = [item.model_dump(mode="json") for item in value]
        else:
            payload = value.model_dump(mode="json")
        console.print_json(json.dumps(payload))
    except GreenBoostError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command("health")
def health() -> None:
    """Check GreenBoost through the public GBIP client."""
    _print("health")


@app.command("discover")
def discover() -> None:
    """List nodes discovered by GreenBoost through GBIP."""
    _print("discover")


@app.command("snapshot")
def snapshot() -> None:
    """Fetch the current typed GreenBoost resource snapshot."""
    _print("snapshot")


@app.command("doctor")
def doctor() -> None:
    console.print_json(json.dumps(GreenBoostRuntime().doctor()))


@app.command("status")
def status() -> None:
    console.print_json(json.dumps(GreenBoostRuntime().snapshot()))


@app.command("plan")
def plan(task: str = typer.Option(..., "--task")) -> None:
    console.print_json(json.dumps(GreenBoostRuntime().plan(task)))
