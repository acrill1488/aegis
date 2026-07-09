from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("create-task")
def create_task(
    goal: str = typer.Argument(..., metavar="GOAL"),
    priority: int = typer.Option(50, "--priority", "-p"),
    task_id: str | None = typer.Option(None, "--id"),
    constraints_json: str = typer.Option("{}", "--constraints-json"),
    constraints_file: Path | None = typer.Option(None, "--constraints-file"),
    metadata_json: str = typer.Option("{}", "--metadata-json"),
    metadata_file: Path | None = typer.Option(None, "--metadata-file"),
):
    """Create a Task Planning Runtime task."""
    constraints = _load_object(constraints_json, constraints_file, "constraints")
    metadata = _load_object(metadata_json, metadata_file, "metadata")
    task = AegisCore().task_planning_runtime.create_task(
        goal=goal,
        priority=priority,
        constraints=constraints,
        metadata=metadata,
        task_id=task_id,
    )
    console.print_json(data=to_plain(task))


@app.command("create-plan")
def create_plan(
    task_id: str = typer.Argument(..., metavar="TASK_ID"),
    plan_id: str | None = typer.Option(None, "--id"),
    metadata_json: str = typer.Option("{}", "--metadata-json"),
    metadata_file: Path | None = typer.Option(None, "--metadata-file"),
):
    """Create a declarative execution graph plan for a task."""
    metadata = _load_object(metadata_json, metadata_file, "metadata")
    runtime = AegisCore().task_planning_runtime
    try:
        plan = runtime.create_plan(
            task_id=task_id,
            metadata=metadata,
            plan_id=plan_id,
        )
    except KeyError as exc:
        console.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(plan))


@app.command("tasks")
def list_tasks(json_output: bool = typer.Option(False, "--json")):
    """List Task Planning Runtime tasks."""
    tasks = AegisCore().task_planning_runtime.list_tasks()
    if json_output:
        console.print_json(data=to_plain(tasks))
        return

    table = Table(title="Task Planning Tasks")
    table.add_column("ID")
    table.add_column("Priority")
    table.add_column("Goal")
    for task in tasks:
        table.add_row(task.id, str(task.priority), task.goal)
    console.print(table)


@app.command("plans")
def list_plans(json_output: bool = typer.Option(False, "--json")):
    """List Task Planning Runtime plans."""
    plans = AegisCore().task_planning_runtime.list_plans()
    if json_output:
        console.print_json(data=to_plain(plans))
        return

    table = Table(title="Task Planning Plans")
    table.add_column("ID")
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Steps")
    for plan in plans:
        table.add_row(
            plan.id,
            plan.task_id,
            plan.status,
            str(len(plan.graph.nodes)),
        )
    console.print(table)


@app.command("execute")
def execute_plan(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Execute a Task Planning Runtime plan sequentially."""
    runtime = AegisCore().task_planning_runtime
    try:
        execution = runtime.execute_plan(plan_id)
    except (KeyError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(execution))


@app.command("execution")
def show_execution(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Show the latest execution for a Task Planning Runtime plan."""
    execution = AegisCore().task_planning_runtime.get_plan_execution(plan_id)
    if execution is None:
        console.print(f"[red]Execution not found for plan: {plan_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(execution))


@app.command("show-task")
def show_task(task_id: str = typer.Argument(..., metavar="TASK_ID")):
    """Show one Task Planning Runtime task."""
    task = AegisCore().task_planning_runtime.get_task(task_id)
    if task is None:
        console.print(f"[red]Task not found: {task_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(task))


@app.command("show-plan")
def show_plan(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Show one Task Planning Runtime plan with graph nodes and edges."""
    plan = AegisCore().task_planning_runtime.get_plan(plan_id)
    if plan is None:
        console.print(f"[red]Plan not found: {plan_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(plan))


def _load_object(
    json_value: str,
    file_path: Path | None,
    label: str,
) -> dict[str, Any]:
    if file_path is not None:
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            console.print(f"[red]Cannot read {label} file:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    else:
        text = json_value

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid {label} JSON:[/red] {exc.msg}")
        console.print(f"[yellow]Location:[/yellow] line {exc.lineno}, column {exc.colno}")
        raise typer.Exit(code=1) from exc

    if not isinstance(value, dict):
        console.print(f"[red]{label} JSON must be an object.[/red]")
        raise typer.Exit(code=1)
    return value
