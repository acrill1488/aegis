"""CLI commands for the AEGIS daemon."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from aegis.daemon.client import DaemonClient
from aegis.daemon.server import serve_ipc
from aegis.ipc import IPCClient, IPCConnectionError
from aegis.serialization import to_json

app = typer.Typer()
console = Console()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
    headless_browser: bool = typer.Option(False, "--headless-browser/--headed-browser"),
):
    """Run the foreground AEGIS daemon IPC server."""
    try:
        serve_ipc(
            host=host,
            port=port,
            headless_browser=headless_browser,
            on_ready=lambda: console.print(f"AEGIS daemon IPC running at {host}:{port}"),
        )
    except KeyboardInterrupt:
        return
    except OSError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def health(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
):
    """Check daemon health."""
    _print_json(_ipc_request(host, port, "health", "status"))


@app.command()
def status(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
):
    """Show daemon status."""
    _print_json(_ipc_request(host, port, "health", "status"))


@app.command()
def services(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
):
    """List daemon services."""
    _print_json(_ipc_request(host, port, "services", "list"))


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
    console.print_json(to_json(data))


def _ipc_request(host: str, port: int, target: str, action: str) -> Any:
    try:
        return IPCClient(host=host, port=port).request(target, action)
    except IPCConnectionError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
