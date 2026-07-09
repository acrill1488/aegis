import json

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_json, to_plain

app = typer.Typer()
console = Console()


@app.command("list")
def list_events(
    limit: int = typer.Option(100, "--limit", "-n"),
    type: str | None = typer.Option(None, "--type"),
    mission_id: str | None = typer.Option(None, "--mission-id"),
    project_id: str | None = typer.Option(None, "--project-id"),
    correlation_id: str | None = typer.Option(None, "--correlation-id"),
    json_output: bool = typer.Option(False, "--json"),
):
    """List universal AEGIS events."""
    events = AegisCore().event_platform.list(
        limit=limit,
        type=type,
        mission_id=mission_id,
        project_id=project_id,
        correlation_id=correlation_id,
    )
    _render_events("Events", events, json_output=json_output)


@app.command("timeline")
def timeline(
    mission_id: str | None = typer.Option(None, "--mission-id"),
    project_id: str | None = typer.Option(None, "--project-id"),
    correlation_id: str | None = typer.Option(None, "--correlation-id"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Show chronological event timeline."""
    events = AegisCore().event_platform.timeline(
        mission_id=mission_id,
        project_id=project_id,
        correlation_id=correlation_id,
    )
    _render_events("Event Timeline", events, json_output=json_output)


@app.command("replay")
def replay(
    correlation_id: str | None = typer.Option(None, "--correlation-id"),
    mission_id: str | None = typer.Option(None, "--mission-id"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Replay events for a mission or correlation chain."""
    events = AegisCore().event_platform.replay(
        correlation_id=correlation_id,
        mission_id=mission_id,
    )
    _render_events("Event Replay", events, json_output=json_output)


@app.command("stats")
def stats():
    """Show event platform stats."""
    console.print_json(data=to_plain(AegisCore().event_platform.stats()))


@app.command("publish")
def publish(
    event_type: str = typer.Argument(..., metavar="TYPE"),
    source: str = typer.Option(..., "--source", "-s"),
    payload_json: str = typer.Option("{}", "--payload-json"),
):
    """Publish an AEGIS event."""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid --payload-json:[/red] {exc.msg}")
        console.print('[yellow]Example:[/yellow] --payload-json "{\\"key\\": \\"value\\"}"')
        raise typer.Exit(code=1) from exc

    if not isinstance(payload, dict):
        console.print("[red]Payload JSON must be an object.[/red]")
        raise typer.Exit(code=1)

    receipt = AegisCore().event_platform.publish(event_type, source, payload)
    console.print(
        f"[green]Published event[/green] {receipt.event_id} "
        f"(delivered={receipt.delivered}, failed={receipt.failed})"
    )


@app.command("history")
def history(limit: int = typer.Option(50, "--limit", "-n")):
    """Show recent AEGIS events."""
    events = list(reversed(AegisCore().event_platform.list(limit=limit)))
    _render_events("Event History", events)


def _render_events(title: str, events, *, json_output: bool = False) -> None:
    if json_output:
        console.print_json(data=to_plain([event.to_dict() for event in events]))
        return

    table = Table(title=title)
    table.add_column("Time")
    table.add_column("Type")
    table.add_column("Severity")
    table.add_column("Source")
    table.add_column("Mission")
    table.add_column("Correlation")
    table.add_column("Payload")

    for event in events:
        table.add_row(
            event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            event.type,
            event.severity,
            event.source,
            event.mission_id or "",
            event.correlation_id or "",
            to_json(event.payload, indent=None),
        )
    console.print(table)
