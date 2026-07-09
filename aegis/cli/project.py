from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("create")
def create_project(
    name: str = typer.Argument(..., metavar="NAME"),
    description: str = typer.Option("", "--description", "-d"),
):
    """Create a Project container."""
    project = AegisCore().project_runtime.create(name, description=description)
    console.print_json(data=to_plain(project))


@app.command("list")
def list_projects():
    """List Projects."""
    projects = AegisCore().project_runtime.list()
    table = Table(title="Projects")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Missions")
    table.add_column("Workspace")
    for project in projects:
        table.add_row(
            project.id,
            project.name,
            project.status,
            str(len(project.mission_ids)),
            project.workspace_path,
        )
    console.print(table)


@app.command("show")
def show_project(project_id: str = typer.Argument(..., metavar="PROJECT_ID")):
    """Show Project details."""
    runtime = AegisCore().project_runtime
    try:
        project = runtime.details(project_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(project))


@app.command("active")
def active_project():
    """Show active Project."""
    project = AegisCore().project_runtime.get_active()
    if project is None:
        console.print("[yellow]No active project[/yellow]")
        return
    console.print_json(data=to_plain(project))


@app.command("set-active")
def set_active_project(project_id: str = typer.Argument(..., metavar="PROJECT_ID")):
    """Set active Project."""
    runtime = AegisCore().project_runtime
    try:
        project = runtime.set_active(project_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(project))


@app.command("status")
def project_status(project_id: str = typer.Argument(..., metavar="PROJECT_ID")):
    """Show Project status."""
    runtime = AegisCore().project_runtime
    try:
        status = runtime.status(project_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(status))


@app.command("artifacts")
def project_artifacts(project_id: str | None = typer.Argument(None, metavar="PROJECT_ID")):
    """List Project artifacts."""
    runtime = AegisCore().project_runtime
    try:
        project_id = _resolve_project_id(runtime, project_id)
        artifacts = runtime.artifacts(project_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(artifacts))


@app.command("missions")
def project_missions(project_id: str | None = typer.Argument(None, metavar="PROJECT_ID")):
    """List Project missions."""
    runtime = AegisCore().project_runtime
    try:
        project_id = _resolve_project_id(runtime, project_id)
        missions = runtime.missions(project_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(missions))


@app.command("reports")
def project_reports(project_id: str | None = typer.Argument(None, metavar="PROJECT_ID")):
    """List Project reports."""
    runtime = AegisCore().project_runtime
    try:
        project_id = _resolve_project_id(runtime, project_id)
        reports = runtime.reports(project_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(reports))


def _resolve_project_id(runtime, project_id: str | None) -> str:
    if project_id:
        return project_id
    project = runtime.get_active()
    if project is None:
        raise KeyError("No active project")
    return project.id
