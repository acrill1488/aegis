"""CLI commands for OCR Runtime."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_json

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
def doctor(verbose: bool = typer.Option(False, "--verbose", "-v")):
    """Diagnose OCR Runtime provider wiring."""
    report = _runtime().doctor(verbose=verbose)
    console.print("[bold]OCR Doctor[/bold]")
    console.print(f"Platform: {report['platform']}")
    console.print(f"Default Provider: {report['default_provider']}")
    console.print(f"Available: {', '.join(report['available']) or '-'}")
    console.print(f"Overall: {report['overall']}")
    console.print(f"Model Checks: {'yes' if report['models_checked'] else 'no'}")
    states = report.get("states") or {}
    if states:
        console.print(
            "States: "
            + ", ".join(f"{key}={value}" for key, value in sorted(states.items()))
        )
    if verbose:
        unlimited = next(
            (item for item in report["providers"] if item["name"] == "unlimited"),
            None,
        )
        details = unlimited.get("doctor", {}) if unlimited else {}
        if details:
            console.print(f"Service URL: {details.get('base_url', '-')}")
            console.print(
                f"Configuration source: {details.get('configuration_source', '-')}"
            )
            console.print(f"Service reachable: {states.get('service_reachable', False)}")
            console.print(f"Service alive: {states.get('service_alive', False)}")
            console.print(f"Model ready: {states.get('model_ready', False)}")
            console.print(f"Model loaded: {states.get('model_loaded', False)}")
            console.print(f"GPU detected: {states.get('gpu_detected', False)}")
            console.print(f"Recognition ready: {states.get('recognition_ready', False)}")

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


@app.command("recognize-image")
def recognize_image(
    source: Path = typer.Argument(..., metavar="SOURCE"),
    language: str | None = typer.Option(None, "--language"),
    provider: str | None = typer.Option(None, "--provider"),
    output: Path | None = typer.Option(None, "--output"),
    json_output: bool = typer.Option(False, "--json"),
    greenboost: bool | None = typer.Option(None, "--greenboost/--no-greenboost"),
):
    """Recognize text from an image."""
    runtime = _runtime()
    result = runtime.recognize_image(
        source,
        language=language,
        provider=provider,
        options={**_recognize_options(output), "greenboost": greenboost},
    )
    _print_result(result, json_output=json_output)
    if result.errors:
        raise typer.Exit(code=1)


@app.command("recognize-pdf")
def recognize_pdf(
    source: Path = typer.Argument(..., metavar="SOURCE"),
    language: str | None = typer.Option(None, "--language"),
    provider: str | None = typer.Option(None, "--provider"),
    output: Path | None = typer.Option(None, "--output"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Recognize text from a PDF."""
    runtime = _runtime()
    result = runtime.recognize_pdf(
        source,
        language=language,
        provider=provider,
        options=_recognize_options(output),
    )
    _print_result(result, json_output=json_output)
    if result.errors:
        raise typer.Exit(code=1)


@app.command("recognize")
def recognize(
    source: Path = typer.Argument(..., metavar="SOURCE"),
    kind: str = typer.Option("image", "--kind"),
    language: str | None = typer.Option(None, "--language"),
    provider: str | None = typer.Option(None, "--provider"),
    output: Path | None = typer.Option(None, "--output"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Recognize text from an image, PDF, document, or directory."""
    runtime = _runtime()
    options = _recognize_options(output)
    if kind == "pdf":
        result = runtime.recognize_pdf(source, language=language, provider=provider, options=options)
    elif kind == "document":
        result = runtime.recognize_document(source, language=language, provider=provider, options=options)
    elif kind == "directory":
        result = runtime.recognize_directory(source, language=language, provider=provider, options=options)
    else:
        result = runtime.recognize_image(source, language=language, provider=provider, options=options)
    _print_result(result, json_output=json_output)
    if result.errors:
        raise typer.Exit(code=1)


def _recognize_options(output: Path | None) -> dict:
    return {"output_dir": str(output)} if output is not None else {}


def _print_result(result, *, json_output: bool) -> None:
    if json_output:
        console.print(to_json(result))
        return
    console.print(f"Provider: {result.provider}")
    console.print(f"Source: {result.source}")
    console.print(f"Processing time: {result.processing_time:.3f}s")
    console.print(f"Pages: {len(result.pages)}")
    console.print(f"Blocks: {len(result.blocks)}")
    console.print(f"Text length: {len(result.text or '')}")
    if result.warnings:
        console.print("Warnings: " + "; ".join(result.warnings))
    artifact_paths = list(dict.fromkeys(
        artifact.get("path")
        for artifact in result.artifacts
        if isinstance(artifact, dict) and artifact.get("path")
    ))
    if artifact_paths:
        console.print("Artifacts:")
        for path in artifact_paths:
            console.print(f"  {path}")
    if result.errors:
        for error in result.errors:
            console.print(f"[red]{error}[/red]")
    elif result.text:
        console.print(result.text)


def _runtime():
    return AegisCore().ocr
