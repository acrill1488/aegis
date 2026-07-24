"""CLI commands for Document Intelligence Runtime."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.document import StructuredDocumentSerializer, StructuredDocumentValidator
from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()
serializer = StructuredDocumentSerializer()
validator = StructuredDocumentValidator()


@app.command("validate")
def validate(path: Path = typer.Argument(..., metavar="DOCUMENT_JSON")):
    """Validate a Structured Document JSON file."""
    document = serializer.from_json(path)
    result = validator.validate(document)
    console.print_json(data=to_plain(result))
    if not result.valid:
        raise typer.Exit(code=1)


@app.command("inspect")
def inspect(path: Path = typer.Argument(..., metavar="DOCUMENT_JSON")):
    """Inspect Structured Document metadata and statistics."""
    document = serializer.from_json(path)
    validation = validator.validate(document)
    table = Table(title="Structured Document")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("ID", document.id)
    table.add_row("Provider", document.provider)
    table.add_row("Language", document.language)
    table.add_row("Source", str(document.source))
    table.add_row("Pages", str(document.statistics.get("page_count", len(document.pages))))
    table.add_row("Blocks", str(document.statistics.get("block_count", 0)))
    table.add_row("Tables", str(document.statistics.get("table_count", 0)))
    table.add_row("Valid", "yes" if validation.valid else "no")
    console.print(table)
    if validation.errors:
        console.print("[red]Errors:[/red] " + "; ".join(validation.errors))
    if validation.warnings:
        console.print("Warnings: " + "; ".join(validation.warnings))


@app.command("export")
def export(
    path: Path = typer.Argument(..., metavar="DOCUMENT_JSON"),
    format: str = typer.Option("markdown", "--format", "-f"),
    output: Path | None = typer.Option(None, "--output", "-o"),
):
    """Export a Structured Document as json, markdown, or plain text."""
    document = serializer.from_json(path)
    if format == "json":
        content = serializer.to_json(document)
        default_suffix = ".json"
    elif format in ("text", "plain", "txt"):
        content = serializer.to_plain_text(document)
        default_suffix = ".txt"
    elif format in ("markdown", "md"):
        content = serializer.to_markdown(document)
        default_suffix = ".md"
    else:
        console.print("[red]Unsupported format. Use json, markdown, or text.[/red]")
        raise typer.Exit(code=1)

    if output is None:
        console.print(content)
        return
    target = output
    if target.is_dir():
        target = target / f"{path.stem}{default_suffix}"
    target.write_text(content, encoding="utf-8")
    console.print(str(target))


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
