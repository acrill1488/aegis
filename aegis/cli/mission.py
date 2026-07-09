from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_json, to_plain
from .daemon_guard import ensure_daemon_running

app = typer.Typer()
console = Console()


@app.command("create")
def create_mission(
    text: str = typer.Argument(..., metavar="TEXT"),
    priority: int = typer.Option(50, "--priority", "-p"),
):
    """Create a Mission from a natural-language goal."""
    core = AegisCore()
    goal = core.goal_engine.parse(text)
    if goal.metadata.get("status") == "unresolved":
        console.print("[red]Goal unresolved[/red]")
        raise typer.Exit(code=1)
    if goal.metadata.get("status") == "not_available":
        console.print(f"[red]Skill not available: {goal.selected_skill}[/red]")
        raise typer.Exit(code=1)
    mission = core.mission_runtime.create(
        goal,
        priority=priority,
        metadata={"source": "cli"},
    )
    console.print_json(data=to_plain(mission))


@app.command("run")
def run_mission(mission_id: str = typer.Argument(..., metavar="ID")):
    """Run a Mission graph."""
    ensure_daemon_running(console)
    runtime = AegisCore().mission_runtime
    try:
        result = runtime.run(mission_id)
    except (KeyError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(result))
    if not result.success:
        raise typer.Exit(code=1)


@app.command("show")
def show_mission(mission_id: str = typer.Argument(..., metavar="ID")):
    """Show a Mission definition and node state."""
    runtime = AegisCore().mission_runtime
    try:
        mission = runtime.show(mission_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(mission))


@app.command("status")
def mission_status(mission_id: str = typer.Argument(..., metavar="ID")):
    """Show Mission status."""
    runtime = AegisCore().mission_runtime
    try:
        status = runtime.status(mission_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(status))


@app.command("timeline")
def mission_timeline(
    mission_id: str = typer.Argument(..., metavar="MISSION_ID"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Show Mission event timeline."""
    events = AegisCore().event_platform.timeline(mission_id=mission_id)
    if json_output:
        console.print_json(data=to_plain([event.to_dict() for event in events]))
        return

    table = Table(title=f"Mission Timeline: {mission_id}")
    table.add_column("Time")
    table.add_column("Type")
    table.add_column("Severity")
    table.add_column("Source")
    table.add_column("Payload")
    for event in events:
        table.add_row(
            event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            event.type,
            event.severity,
            event.source,
            to_json(event.payload, indent=None),
        )
    console.print(table)


@app.command("list")
def list_missions(json_output: bool = typer.Option(False, "--json")):
    """List Missions."""
    missions = AegisCore().mission_runtime.list()
    if json_output:
        console.print_json(data=to_plain(missions))
        return

    table = Table(title="Missions")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Skills")
    table.add_column("Goal")
    for mission in missions:
        table.add_row(
            mission.id,
            mission.status,
            str(mission.priority),
            str(len(mission.graph)),
            mission.goal,
        )
    console.print(table)
