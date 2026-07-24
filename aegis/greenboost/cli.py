"""GreenBoost system resource commands."""

import json

import typer
from rich.console import Console

from .runtime import GreenBoostRuntime

app = typer.Typer()
console = Console()


@app.command("doctor")
def doctor() -> None:
    console.print_json(json.dumps(GreenBoostRuntime().doctor()))


@app.command("status")
def status() -> None:
    console.print_json(json.dumps(GreenBoostRuntime().snapshot()))


@app.command("plan")
def plan(task: str = typer.Option(..., "--task")) -> None:
    console.print_json(json.dumps(GreenBoostRuntime().plan(task)))
