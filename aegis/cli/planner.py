from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("context")
def context(goal: str = typer.Argument(..., metavar="GOAL")):
    """Build Adaptive Planner context for a goal."""
    runtime = AegisCore().adaptive_planner
    planner_context = runtime.build_context(goal)
    console.print_json(data=to_plain(planner_context))


@app.command("plan")
def plan(goal: str = typer.Argument(..., metavar="GOAL")):
    """Create a heuristic Adaptive Planner plan."""
    runtime = AegisCore().adaptive_planner
    planner_plan = runtime.plan(goal)
    table = Table(title=f"Planner Plan {planner_plan.id}")
    table.add_column("Step")
    table.add_column("Skill")
    table.add_column("Confidence")
    table.add_column("Dependencies")
    if planner_plan.graph is not None:
        for step in planner_plan.graph.nodes:
            table.add_row(
                step.id,
                step.skill_id,
                f"{step.confidence:.2f}",
                ", ".join(step.dependencies) or "-",
            )
    console.print(table)
    if planner_plan.warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in planner_plan.warnings:
            console.print(f"- {warning}")


@app.command("explain")
def explain(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Explain a saved Adaptive Planner plan."""
    runtime = AegisCore().adaptive_planner
    try:
        console.print(runtime.explain(plan_id), markup=False)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command("validate")
def validate(plan_id: str = typer.Argument(..., metavar="PLAN_ID")):
    """Validate a saved Adaptive Planner plan graph."""
    runtime = AegisCore().adaptive_planner
    try:
        result = runtime.validate(plan_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(result))
    if not result["valid"]:
        raise typer.Exit(code=1)
