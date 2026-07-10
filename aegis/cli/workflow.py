"""CLI commands for Workflow Library Runtime."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain
from aegis.workflow_library import WorkflowLibraryRuntime

app = typer.Typer()
console = Console()


@app.command("scan")
def scan(root: str | None = typer.Option(None, "--root")):
    """Scan workflow JSON files into the catalog."""
    workflows = _runtime().scan(root)
    _print_workflows(workflows, title="Workflow Library Scan")


@app.command("list")
def list_workflows(
    category: str | None = typer.Option(None, "--category"),
    task_type: str | None = typer.Option(None, "--task-type"),
):
    """List workflow templates."""
    _print_workflows(_runtime().list(category=category, task_type=task_type), title="Workflow Library")


@app.command("search")
def search(query: str = typer.Argument(..., metavar="QUERY")):
    """Search workflow templates."""
    _print_workflows(_runtime().search(query), title=f"Workflow Search: {query}")


@app.command("show")
def show(workflow_id: str = typer.Argument(..., metavar="WORKFLOW_ID")):
    """Show one workflow template."""
    workflow = _runtime().get(workflow_id)
    if workflow is None:
        console.print(f"[red]Workflow not found:[/red] {workflow_id}")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(workflow))


@app.command("validate")
def validate(workflow_id: str = typer.Argument(..., metavar="WORKFLOW_ID")):
    """Validate required models and workflow file presence."""
    result = _runtime().validate(workflow_id)
    console.print_json(data=to_plain(result))
    if not result.success:
        raise typer.Exit(code=1)


@app.command("select")
def select(
    task_type: str = typer.Option(..., "--task-type"),
    model_family: str | None = typer.Option(None, "--model-family"),
    tags: list[str] | None = typer.Option(None, "--tag"),
):
    """Select the best workflow for a task."""
    workflow = _runtime().select(task_type=task_type, model_family=model_family, tags=tags)
    if workflow is None:
        console.print("[red]No matching workflow found[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(workflow))


def _print_workflows(workflows, title: str) -> None:
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Task")
    table.add_column("Family")
    table.add_column("Path")
    for workflow in workflows:
        table.add_row(
            workflow.id,
            workflow.name,
            workflow.category,
            workflow.task_type,
            workflow.model_family,
            workflow.path,
        )
    console.print(table)


def _runtime() -> WorkflowLibraryRuntime:
    return AegisCore().image_generation.workflow_library
