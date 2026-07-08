"""CLI commands for the AEGIS daemon."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console

from aegis.daemon.client import DaemonClient

app = typer.Typer()
console = Console()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
):
    """Run the AEGIS daemon."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]uvicorn is not installed.[/red] "
            "Install dependencies from requirements/base.txt."
        )
        raise typer.Exit(code=1)

    uvicorn.run(
        "aegis.daemon.server:create_app",
        factory=True,
        host=host,
        port=port,
    )


@app.command()
def health(base_url: str = typer.Option("http://127.0.0.1:8765", "--base-url")):
    """Check daemon health."""
    _print_json(DaemonClient(base_url=base_url).health())


@app.command()
def status(base_url: str = typer.Option("http://127.0.0.1:8765", "--base-url")):
    """Show daemon status."""
    _print_json(DaemonClient(base_url=base_url).status())


@app.command()
def ask(
    prompt: str = typer.Argument(...),
    capability: str = typer.Option("auto", "--capability", "-c"),
    role: str = typer.Option("assistant", "--role", "-r"),
    base_url: str = typer.Option("http://127.0.0.1:8765", "--base-url"),
):
    """Ask through the daemon."""
    response = DaemonClient(base_url=base_url).ask(prompt, capability, role)
    console.print(response.get("response", ""))


@app.command()
def events(base_url: str = typer.Option("http://127.0.0.1:8765", "--base-url")):
    """Show daemon event history."""
    _print_json(DaemonClient(base_url=base_url).events_history())


def _print_json(data: Any) -> None:
    console.print_json(json.dumps(data, ensure_ascii=False))
