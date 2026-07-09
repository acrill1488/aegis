"""CLI commands for Document Intelligence Runtime."""

from pathlib import Path

import typer
from rich.console import Console

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("extract")
def extract(path: Path = typer.Argument(..., metavar="PATH")):
    """Extract text from a supported document."""
    console.print_json(data=to_plain(_runtime().extract(path)))


@app.command("add-to-knowledge")
def add_to_knowledge(path: Path = typer.Argument(..., metavar="PATH")):
    """Extract a document and add the result to Knowledge Runtime."""
    console.print_json(data=to_plain(_runtime().add_to_knowledge(path)))


@app.command("supported-types")
def supported_types():
    """List supported document types."""
    console.print_json(data=to_plain(_runtime().supported_types()))


def _runtime():
    return AegisCore().document
