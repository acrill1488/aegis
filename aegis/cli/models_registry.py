from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.models import ModelRegistry
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("seed")
def seed_registry():
    """Seed the model registry with default model records."""
    registry = ModelRegistry()
    added = registry.seed_defaults()
    console.print_json(data={"added": added})


@app.command("list")
def list_models(
    task: str | None = typer.Option(None, "--task", help="Filter by task type"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print JSON instead of a table",
    ),
):
    """List registered models."""
    core = AegisCore()
    records = core.model_registry.list(task_type=task)
    if json_output:
        console.print_json(data=to_plain(records))
        return

    table = Table(title="AEGIS Model Registry")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Provider")
    table.add_column("Tasks")
    table.add_column("Enabled")
    table.add_column("Quality")
    table.add_column("Speed")

    for record in records:
        table.add_row(
            record.id,
            record.name,
            record.provider,
            ", ".join(record.task_types),
            "yes" if record.enabled else "no",
            record.quality_tier,
            record.speed_tier,
        )

    console.print(table)


@app.command("show")
def show_model(model_id: str = typer.Argument(..., metavar="MODEL_ID")):
    """Show one model registry record."""
    core = AegisCore()
    record = core.model_registry.get(model_id)
    if record is None:
        console.print(f"[red]Model not found: {model_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(record))


@app.command("enable")
def enable_model(model_id: str = typer.Argument(..., metavar="MODEL_ID")):
    """Enable a model for routing eligibility."""
    core = AegisCore()
    try:
        record = core.model_registry.enable(model_id)
    except KeyError as exc:
        console.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(record))


@app.command("disable")
def disable_model(model_id: str = typer.Argument(..., metavar="MODEL_ID")):
    """Disable a model for routing eligibility."""
    core = AegisCore()
    try:
        record = core.model_registry.disable(model_id)
    except KeyError as exc:
        console.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(record))


@app.command("remove")
def remove_model(model_id: str = typer.Argument(..., metavar="MODEL_ID")):
    """Remove a model registry record."""
    core = AegisCore()
    removed = core.model_registry.remove(model_id)
    if not removed:
        console.print(f"[red]Model not found: {model_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data={"removed": True, "model_id": model_id})
