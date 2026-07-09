from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.mcp_runtime import MCPServerRecord
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("servers")
def list_servers():
    """List registered MCP servers."""
    core = AegisCore()
    table = Table(title="AEGIS MCP Servers")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Command")
    table.add_column("Enabled")
    table.add_column("Status")
    table.add_column("Capabilities")

    for record in core.mcp_runtime.list_servers():
        table.add_row(
            record.id,
            record.name,
            " ".join([record.command, *record.args]).strip(),
            "yes" if record.enabled else "no",
            record.status,
            ", ".join(record.capabilities) or "-",
        )

    console.print(table)


@app.command("add")
def add_server(
    server_id: str = typer.Argument(..., metavar="SERVER_ID"),
    name: str = typer.Option(..., "--name", "-n"),
    command: str = typer.Option(..., "--command", "-c"),
    arg: list[str] = typer.Option([], "--arg", help="Command argument"),
    capability: list[str] = typer.Option(
        [],
        "--capability",
        help="Capability advertised by this MCP server",
    ),
):
    """Register an MCP server as an external capability provider."""
    core = AegisCore()
    record = MCPServerRecord(
        id=server_id,
        name=name,
        command=command,
        args=list(arg),
        capabilities=list(capability),
    )
    registered = core.mcp_runtime.register_server(record)
    console.print_json(data=to_plain(registered))


@app.command("show")
def show_server(server_id: str = typer.Argument(..., metavar="SERVER_ID")):
    """Show one MCP server record."""
    core = AegisCore()
    record = core.mcp_runtime.registry.get(server_id)
    if record is None:
        console.print(f"[red]MCP server not found: {server_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(record))


@app.command("enable")
def enable_server(server_id: str = typer.Argument(..., metavar="SERVER_ID")):
    """Enable an MCP server for discovery."""
    core = AegisCore()
    try:
        record = core.mcp_runtime.registry.enable(server_id)
    except KeyError as exc:
        console.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(record))


@app.command("disable")
def disable_server(server_id: str = typer.Argument(..., metavar="SERVER_ID")):
    """Disable an MCP server for discovery."""
    core = AegisCore()
    try:
        record = core.mcp_runtime.registry.disable(server_id)
    except KeyError as exc:
        console.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(record))


@app.command("remove")
def remove_server(server_id: str = typer.Argument(..., metavar="SERVER_ID")):
    """Remove an MCP server record."""
    core = AegisCore()
    removed = core.mcp_runtime.registry.remove(server_id)
    if not removed:
        console.print(f"[red]MCP server not found: {server_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data={"removed": True, "server_id": server_id})


@app.command("discover")
def discover_server(server_id: str = typer.Argument(..., metavar="SERVER_ID")):
    """Register an MCP server's configured capabilities."""
    result = AegisCore().mcp_runtime.discover(server_id)
    console.print_json(data=to_plain(result))
    if result["status"] == "not_found":
        raise typer.Exit(code=1)
