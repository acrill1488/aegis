from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.models.requests import ModelRequest
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("health")
def health():
    """Show Model Runtime provider health."""
    core = AegisCore()
    health_payload = {
        provider_id: provider.health()
        for provider_id, provider in core.model_runtime.providers.items()
    }
    console.print_json(data=health_payload)


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
