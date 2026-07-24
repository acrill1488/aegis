"""CLI for the embedding runtime."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.serialization import to_plain

from .doctor import EmbeddingDoctor
from .errors import EmbeddingError, EmbeddingValidationError
from .models import EmbeddingRequest
from .runtime import EmbeddingRuntime

app = typer.Typer()
console = Console()


def _runtime() -> EmbeddingRuntime:
    return EmbeddingRuntime()


def _json(value: object) -> str:
    return json.dumps(to_plain(value), ensure_ascii=False, indent=2, allow_nan=False)


def _fail(exc: Exception, json_output: bool) -> None:
    code = exc.code if isinstance(exc, EmbeddingError) else "embeddings.provider.failed"
    payload = {"errors": [{"type": code, "message": str(exc)}]}
    typer.echo(_json(payload) if json_output else str(exc))
    raise typer.Exit(code=1)


@app.command("providers")
def providers(json_output: bool = typer.Option(False, "--json")):
    """List embedding providers without loading a model."""
    rows = _runtime().providers()
    if json_output:
        typer.echo(_json({"providers": rows}))
        return
    table = Table(title="Embedding Providers")
    for column in ("Provider", "Available", "Default", "Device", "Status"):
        table.add_column(column)
    for row in rows:
        table.add_row(row["id"], "yes" if row["available"] else "no", "yes" if row["default"] else "no", row["device"], row["status"])
    console.print(table)


@app.command("doctor")
def doctor(provider: str | None = typer.Argument(None), json_output: bool = typer.Option(False, "--json")):
    """Inspect package, device and cache state without loading the model."""
    try:
        runtime = _runtime()
        report = EmbeddingDoctor(runtime.registry).report(provider)
    except Exception as exc:
        _fail(exc, json_output)
    if json_output:
        typer.echo(_json(report))
        return
    selected = report["selected_provider"]
    console.print("[bold]Embedding Platform Status[/bold]")
    console.print(f"Embedding Platform Overall: {report['overall']}")
    console.print(f"Default Provider: {report['default_provider']}")
    console.print("[bold]Selected Provider Status[/bold]")
    console.print(f"Selected Provider: {selected['id']}")
    console.print(f"Selected Provider Overall: {selected['overall']}")
    console.print(f"Available: {str(selected['available']).lower()}")
    console.print(f"Device: {selected['device']}")
    console.print(f"Reason: {selected['status']}")
    console.print(f"Model Loaded: {str(selected['model_loaded']).lower()}")
    cached = selected["model_cached"]
    console.print(f"Model Cached: {'unknown' if cached is None else str(cached).lower()}")
    if selected["message"]:
        console.print(f"Details: {selected['message']}")


def _embed(
    text: str, provider: str | None, device: str | None, batch_size: int | None,
    normalize: bool | None, json_output: bool, show_vector: bool,
) -> None:
    try:
        result = _runtime().embed(EmbeddingRequest(
            texts=text, provider=provider, device=device, batch_size=batch_size, normalize=normalize,
        ))
    except Exception as exc:
        _fail(exc, json_output)
    if json_output:
        typer.echo(_json(result))
        return
    table = Table(title="Embedding Result")
    table.add_column("Field")
    table.add_column("Value")
    values = {
        "Provider": result.provider, "Model": result.model, "Texts": str(len(result.vectors)),
        "Dimensions": str(result.dimensions), "Normalized": str(result.normalized).lower(),
        "Device": result.device, "Duration": f"{result.duration_ms:.2f} ms",
    }
    if show_vector:
        values["Vector"] = str(result.vectors[0].vector)
    for key, value in values.items():
        table.add_row(key, value)
    console.print(table)


@app.command("embed")
def embed(
    text: str = typer.Argument(...),
    provider: str | None = typer.Option(None, "--provider"),
    device: str | None = typer.Option(None, "--device"),
    batch_size: int | None = typer.Option(None, "--batch-size"),
    normalize: bool | None = typer.Option(None, "--normalize/--no-normalize"),
    json_output: bool = typer.Option(False, "--json"),
    show_vector: bool = typer.Option(False, "--show-vector"),
):
    """Generate a dense embedding using the selected provider."""
    _embed(text, provider, device, batch_size, normalize, json_output, show_vector)


@app.command("embed-file")
def embed_file(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
    provider: str | None = typer.Option(None, "--provider"),
    device: str | None = typer.Option(None, "--device"),
    batch_size: int | None = typer.Option(None, "--batch-size"),
    normalize: bool | None = typer.Option(None, "--normalize/--no-normalize"),
    json_output: bool = typer.Option(False, "--json"),
    show_vector: bool = typer.Option(False, "--show-vector"),
):
    """Embed a UTF-8 .txt or .md file."""
    if path.suffix.lower() not in {".txt", ".md"}:
        _fail(EmbeddingValidationError("embed-file supports only .txt and .md files"), json_output)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        _fail(EmbeddingValidationError(f"Could not read {path}: {exc}"), json_output)
    _embed(text, provider, device, batch_size, normalize, json_output, show_vector)
