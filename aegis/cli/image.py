"""CLI commands for Image Generation Runtime."""

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("generate")
def generate(
    prompt: str = typer.Argument(..., metavar="PROMPT"),
    negative_prompt: str = typer.Option("", "--negative-prompt"),
    width: int = typer.Option(1024, "--width"),
    height: int = typer.Option(1024, "--height"),
    steps: int = typer.Option(20, "--steps"),
    seed: int | None = typer.Option(None, "--seed"),
    style: str = typer.Option("", "--style"),
    output_dir: str = typer.Option("", "--output-dir"),
    provider: str | None = typer.Option(None, "--provider"),
):
    """Generate an image."""
    result = _runtime().generate(
        prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        steps=steps,
        seed=seed,
        style=style,
        output_dir=output_dir,
        provider=provider,
    )
    console.print_json(data=to_plain(result))
    if not result.success:
        raise typer.Exit(code=1)


@app.command("providers")
def providers():
    """Show image generation providers."""
    runtime = _runtime()
    table = Table(title="Image Generation Providers")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Default")
    table.add_column("Mode")
    for provider in runtime.providers():
        capabilities = provider.get("capabilities", {})
        table.add_row(
            str(provider["name"]),
            "yes" if provider["available"] else "no",
            "yes" if provider["default"] else "no",
            str(capabilities.get("mode", "")),
        )
    console.print(table)


def _runtime():
    return AegisCore().image_generation
