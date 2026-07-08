from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.models.requests import ModelRequest
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


def _constraints(
    provider: str | None = None,
    min_context_window: int | None = None,
    quality_tier: str | None = None,
    speed_tier: str | None = None,
    input_modalities: str | None = None,
    output_modalities: str | None = None,
) -> dict:
    constraints: dict = {}
    if provider is not None:
        constraints["provider"] = provider
    if min_context_window is not None:
        constraints["min_context_window"] = min_context_window
    if quality_tier is not None:
        constraints["quality_tier"] = quality_tier
    if speed_tier is not None:
        constraints["speed_tier"] = speed_tier
    if input_modalities is not None:
        constraints["input_modalities"] = _split_modalities(input_modalities)
    if output_modalities is not None:
        constraints["output_modalities"] = _split_modalities(output_modalities)
    return constraints


def _split_modalities(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _model_table(title: str) -> Table:
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Provider")
    table.add_column("Context")
    table.add_column("Quality")
    table.add_column("Speed")
    table.add_column("VRAM GB")
    return table


def _add_model_row(table: Table, record) -> None:
    table.add_row(
        record.id,
        record.name,
        record.provider,
        str(record.context_window or "-"),
        record.quality_tier,
        record.speed_tier,
        str(record.vram_required_gb) if record.vram_required_gb is not None else "-",
    )


@app.command("health")
def health():
    """Show Model Runtime provider health."""
    core = AegisCore()
    health_payload = {
        provider_id: provider.health()
        for provider_id, provider in core.model_runtime.providers.items()
    }
    console.print_json(data=health_payload)


@app.command("route")
def route(
    task: str = typer.Option(..., "--task", help="Task type to route"),
    provider: str | None = typer.Option(None, "--provider", help="Required provider"),
    min_context_window: int | None = typer.Option(
        None,
        "--min-context-window",
        help="Minimum context window",
    ),
    quality_tier: str | None = typer.Option(
        None,
        "--quality-tier",
        help="Minimum quality tier",
    ),
    speed_tier: str | None = typer.Option(
        None,
        "--speed-tier",
        help="Minimum speed tier",
    ),
    input_modalities: str | None = typer.Option(
        None,
        "--input-modalities",
        help="Comma-separated required input modalities",
    ),
    output_modalities: str | None = typer.Option(
        None,
        "--output-modalities",
        help="Comma-separated required output modalities",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print JSON instead of a table",
    ),
):
    """Select the best model for a task."""
    core = AegisCore()
    record = core.model_runtime.route(
        task,
        constraints=_constraints(
            provider=provider,
            min_context_window=min_context_window,
            quality_tier=quality_tier,
            speed_tier=speed_tier,
            input_modalities=input_modalities,
            output_modalities=output_modalities,
        ),
    )
    if record is None:
        console.print_json(data={"selected": None, "task_type": task})
        raise typer.Exit(code=1)

    if json_output:
        console.print_json(data=to_plain(record))
        return

    table = _model_table("Model Runtime Route")
    _add_model_row(table, record)
    console.print(table)


@app.command("candidates")
def candidates(
    task: str = typer.Option(..., "--task", help="Task type to route"),
    enabled_only: bool = typer.Option(
        True,
        "--enabled-only/--all",
        help="Show only enabled candidates",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print JSON instead of a table",
    ),
):
    """List model candidates for a task."""
    core = AegisCore()
    records = core.model_runtime.router.candidates(
        task_type=task,
        enabled_only=enabled_only,
    )
    if json_output:
        console.print_json(data=to_plain(records))
        return

    table = _model_table("Model Runtime Candidates")
    for record in records:
        _add_model_row(table, record)
    console.print(table)


@app.command("providers")
def providers():
    """List Model Runtime providers."""
    core = AegisCore()
    table = Table(title="Model Runtime Providers")
    table.add_column("Provider")
    table.add_column("Models")

    for provider_id, provider in core.model_runtime.providers.items():
        try:
            models = provider.list_models()
            model_text = ", ".join(models) if models else "-"
        except Exception as exc:
            model_text = f"error: {exc}"
        table.add_row(provider_id, model_text)

    console.print(table)


@app.command("generate")
def generate(
    task: str = typer.Option("general", "--task", help="Task type to route"),
    prompt: str = typer.Option(..., "--prompt", help="Prompt text"),
):
    """Generate text through Model Runtime."""
    core = AegisCore()
    request = ModelRequest(task_type=task, input={"prompt": prompt})
    result = core.model_runtime.generate(request)
    if result.success:
        text = result.output.get("text", "")
        console.print(text)
        return

    console.print_json(data=to_plain(result))
    raise typer.Exit(code=1)
