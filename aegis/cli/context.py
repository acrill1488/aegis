"""CLI commands for Context Builder."""

import typer
from rich.console import Console

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()


@app.command("build")
def build(query: str = typer.Argument(...)):
    """Build prompt-ready context for a query."""
    core = AegisCore()
    bundle = core.context_builder.build(query)
    console.print(core.context_builder.to_prompt_context(bundle), markup=False)
