"""CLI commands for Vision Runtime."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("capture")
def capture():
    """Capture a desktop screenshot."""
    console.print_json(data=to_plain(_runtime().capture()))


@app.command("analyze")
def analyze(image_path: Path | None = typer.Argument(None, metavar="IMAGE_PATH")):
    """Analyze an image with the configured OCR provider."""
    if image_path is None:
        capture_result = _runtime().capture()
        image_path = Path(capture_result["image_path"])
    console.print_json(data=to_plain(_runtime().analyze(str(image_path))))


@app.command("snapshot")
def snapshot():
    """Capture and analyze the desktop."""
    console.print_json(data=to_plain(_runtime().snapshot()))


@app.command("find")
def find(
    query: str = typer.Argument(..., metavar="QUERY"),
    image_path: Path | None = typer.Option(None, "--image", "-i"),
):
    """Find text in a screenshot or image analysis result."""
    console.print_json(data=to_plain(_runtime().find(query, str(image_path) if image_path else None)))


@app.command("providers")
def providers():
    """Show Vision OCR providers."""
    runtime = _runtime()
    table = Table(title="Vision OCR Providers")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Active")
    labels = {
        "unlimited": "Unlimited OCR",
        "stub": "Stub OCR",
    }
    for name in ("unlimited", "stub"):
        provider = runtime.ocr_providers[name]
        available = provider.available()
        table.add_row(
            labels.get(name, name),
            "yes" if available else "no",
            "yes" if name == runtime.default_ocr_provider else "no",
        )
    console.print(table)


def _runtime():
    return AegisCore().vision
