"""CLI integrated with the existing AEGIS root application."""

from __future__ import annotations

import json
import os

import typer
from rich.console import Console
from rich.table import Table

from .config import load_remote_runtime_config

app = typer.Typer(no_args_is_help=True)
console = Console()


def _json(value: object) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


@app.command("nodes")
def nodes(json_output: bool = typer.Option(False, "--json")) -> None:
    """List configured remote compute nodes."""
    config = load_remote_runtime_config()
    rows = [{"id": node.id, "base_url": node.base_url, "enabled": node.enabled,
             "token_configured": bool(node.token), "default": node.id == config.default_node}
            for node in config.nodes.values()]
    if json_output:
        _json({"nodes": rows})
        return
    table = Table(title="AEGIS Remote Nodes")
    for column in ("Node", "URL", "Enabled", "Token", "Default"):
        table.add_column(column)
    for row in rows:
        table.add_row(row["id"], row["base_url"], str(row["enabled"]).lower(),
                      "configured" if row["token_configured"] else "missing", str(row["default"]).lower())
    console.print(table)
    if not rows:
        console.print("No remote nodes configured in services.yaml")


@app.command("doctor")
def doctor(node_id: str | None = typer.Argument(None), json_output: bool = typer.Option(False, "--json")) -> None:
    """Check configuration and remote health without loading a model."""
    config = load_remote_runtime_config()
    selected = []
    for node in config.nodes.values():
        if node_id is not None and node.id != node_id:
            continue
        row = {"id": node.id, "url": node.base_url, "token_configured": bool(node.token)}
        if not node.token:
            row.update(status="NOT READY", reason=f"Set {node.token_env}")
        else:
            try:
                from .client import RemoteRuntimeClient

                health = RemoteRuntimeClient(
                    node, connect_timeout=config.connect_timeout_seconds,
                    read_timeout=config.read_timeout_seconds,
                ).health()
                row.update(status="READY" if health.get("status") == "healthy" else "DEGRADED",
                           reason=health.get("status", "invalid response"))
            except Exception as exc:
                row.update(status="NOT READY", reason=str(exc))
        selected.append(row)
    if json_output:
        _json({"remote_runtime": selected})
        return
    console.print("[bold]AEGIS Remote Runtime[/bold]")
    if not selected:
        console.print("Overall: NOT CONFIGURED")
    for row in selected:
        console.print(f"{row['id']}: {row['status']} - {row['reason']}")


@app.command("providers")
def providers(node: str | None = typer.Option(None, "--node"), json_output: bool = typer.Option(False, "--json")) -> None:
    """List providers exposed by a remote node."""
    config = load_remote_runtime_config()
    try:
        selected = config.node(node)
        from .client import RemoteRuntimeClient

        result = RemoteRuntimeClient(
            selected, connect_timeout=config.connect_timeout_seconds,
            read_timeout=config.read_timeout_seconds,
        ).providers()
    except Exception as exc:
        result = {"providers": [], "errors": [{"type": "remote.node.unavailable", "message": str(exc)}]}
    if json_output:
        _json(result)
        return
    table = Table(title="Remote Providers")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Status")
    for row in result.get("providers", []):
        table.add_row(str(row.get("id")), str(row.get("available", False)).lower(), str(row.get("status", "unknown")))
    console.print(table)
    for error in result.get("errors", []):
        console.print(f"[yellow]{error['message']}[/yellow]")


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(8090, "--port"),
    node_id: str | None = typer.Option(None, "--node-id"),
) -> None:
    """Run the existing AEGIS Remote Runtime Server."""
    if host in {"0.0.0.0", "::"} and not os.environ.get("AEGIS_REMOTE_TOKEN"):
        raise typer.BadParameter("AEGIS_REMOTE_TOKEN is required for an external bind")
    if node_id:
        os.environ["AEGIS_REMOTE_NODE_ID"] = node_id
    import uvicorn

    uvicorn.run("aegis.remote.server.app:app", host=host, port=port)

