"""CLI commands for OCR Runtime."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()


@app.command("providers")
def providers():
    """Show OCR providers."""
    table = Table(title="OCR Providers")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Default")
    table.add_column("Mode")
    table.add_column("Formats")
    for provider in _runtime().providers():
        capabilities = provider.get("capabilities", {})
        table.add_row(
            str(provider["name"]),
            "yes" if provider["available"] else "no",
            "yes" if provider["default"] else "no",
            str(capabilities.get("mode", "")),
            ", ".join(provider.get("supported_formats", [])),
        )
    console.print(table)


@app.command("doctor")
def doctor():
    """Diagnose OCR Runtime provider wiring."""
    report = _runtime().doctor()
    console.print("[bold]OCR Doctor[/bold]")
    console.print(f"Platform: {report['platform']}")
    console.print(f"Default Provider: {report['default_provider']}")
    console.print(f"Available: {', '.join(report['available']) or '-'}")
    console.print(f"Overall: {report['overall']}")
    console.print("Model Checks: skipped")

    table = Table(title="Providers")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Capabilities")
    table.add_column("Supported Formats")
    for provider in report["providers"]:
        capabilities = provider["capabilities"]
        capability_names = [
            key for key, value in capabilities.items() if isinstance(value, bool) and value
        ]
        table.add_row(
            str(provider["name"]),
            "yes" if provider["available"] else "no",
            ", ".join(capability_names) or "-",
            ", ".join(provider["supported_formats"]),
        )
    console.print(table)


@app.command("capabilities")
def capabilities(provider: str | None = typer.Option(None, "--provider")):
    """Show OCR provider capabilities."""
    runtime = _runtime()
    selected = provider or runtime.default_provider()
    data = runtime.capabilities(provider)
    table = Table(title=f"OCR Capabilities: {selected}")
    table.add_column("Capability")
    table.add_column("Value")
    for key in sorted(data):
        value = data[key]
        if isinstance(value, list):
            rendered = ", ".join(str(item) for item in value) or "-"
        else:
            rendered = str(value)
        table.add_row(str(key), rendered)
    console.print(table)


@app.command("recognize")
def recognize(
    source: Path = typer.Argument(..., metavar="SOURCE"),
    kind: str = typer.Option("image", "--kind"),
    language: str | None = typer.Option(None, "--language"),
    provider: str | None = typer.Option(None, "--provider"),
):
    """Foundation placeholder for OCR recognition."""
    runtime = _runtime()
    if kind == "pdf":
        result = runtime.recognize_pdf(source, language=language, provider=provider)
    elif kind == "document":
        result = runtime.recognize_document(source, language=language, provider=provider)
    elif kind == "directory":
        result = runtime.recognize_directory(source, language=language, provider=provider)
    else:
        result = runtime.recognize_image(source, language=language, provider=provider)
    console.print("[yellow]NotImplemented[/yellow]")
    for error in result.errors:
        console.print(f"[red]{error}[/red]")
    raise typer.Exit(code=1)


def _runtime():
    return AegisCore().ocr
