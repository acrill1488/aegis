"""CLI commands for Image Generation Runtime."""

import time

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.image_generation.model_catalog import ImageModelCatalog
from aegis.image_generation.providers.comfyui import ComfyUIProvider

app = typer.Typer()
models_app = typer.Typer(invoke_without_command=True)
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
    workflow: str | None = typer.Option(None, "--workflow"),
    model_family: str | None = typer.Option(None, "--model-family"),
    task_type: str = typer.Option("txt2img", "--task-type"),
    tags: list[str] | None = typer.Option(None, "--tag"),
):
    """Generate an image."""
    core = AegisCore()
    runtime = core.image_generation
    provider_name = provider or runtime.default_provider()
    state = {
        "provider": provider_name,
        "workflow": workflow or "",
        "model_family": model_family or "",
        "seed": str(seed) if seed is not None else "auto",
        "progress": "starting",
        "elapsed": "0.0s",
    }
    started_at = time.monotonic()

    def on_progress(event) -> None:
        payload = event.payload
        state["provider"] = str(payload.get("provider") or state["provider"])
        state["workflow"] = str(payload.get("workflow") or state["workflow"])
        progress = payload.get("progress")
        if isinstance(progress, (int, float)):
            state["progress"] = f"{max(0.0, min(100.0, float(progress) * 100)):.0f}%"
        else:
            state["progress"] = str(payload.get("message") or state["progress"])
        elapsed = payload.get("elapsed")
        if isinstance(elapsed, (int, float)):
            state["elapsed"] = f"{float(elapsed):.1f}s"
        else:
            state["elapsed"] = f"{time.monotonic() - started_at:.1f}s"

    core.events.subscribe("image.generation.progress", on_progress)
    with Live(_progress_table(state), console=console, refresh_per_second=4) as live:
        result = runtime.generate(
            prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            seed=seed,
            style=style,
            output_dir=output_dir,
            provider=provider,
            workflow=workflow,
            model_family=model_family,
            task_type=task_type,
            tags=tags,
        )
        state["provider"] = result.provider or state["provider"]
        state["workflow"] = result.workflow or state["workflow"]
        state["model_family"] = result.model_family or state["model_family"]
        state["seed"] = str(result.seed) if result.seed is not None else state["seed"]
        state["progress"] = "completed" if result.success else "failed"
        state["elapsed"] = f"{result.generation_time:.1f}s"
        live.update(_progress_table(state))

    _print_generation_result(result)
    if not result.success:
        if result.error:
            console.print(f"[red]{result.error}[/red]")
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


@app.command("doctor")
def doctor(verbose: bool = typer.Option(False, "--verbose", "-v")):
    """Diagnose the configured ComfyUI image generation backend."""
    provider = ComfyUIProvider()
    report = provider.doctor(verbose=verbose)

    console.print("[bold]Image Doctor[/bold]")
    console.print(f"Base URL: {report.base_url}")
    console.print(f"Reverse proxy: {report.proxy}")
    console.print(f"Backend: {report.backend_url or 'unknown'}")
    console.print(f"ComfyUI version: {report.comfyui_version}")

    for name in (
        "Network",
        "Reverse Proxy",
        "Backend",
        "Queue",
        "History",
        "Prompt API",
        "View API",
        "Workflow",
        "Output directory",
    ):
        check = next((item for item in report.checks if item.name == name), None)
        if check is None:
            continue
        console.print(f"{name:<18} {_status_label(check.status)}")

    if verbose:
        table = Table(title="Verbose Diagnostics")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("HTTP")
        table.add_column("Time")
        table.add_column("Error type")
        table.add_column("Details")
        for check in report.checks:
            http_status = str(check.status_code) if check.status_code is not None else "-"
            elapsed = f"{check.elapsed_ms:.1f} ms" if check.elapsed_ms is not None else "-"
            detail = check.detail
            if check.headers.get("server"):
                detail = f"{detail}; server={check.headers['server']}"
            table.add_row(
                check.name,
                _status_label(check.status, markup=False),
                http_status,
                elapsed,
                check.error_type or "-",
                detail,
            )
        console.print(table)

    console.print()
    console.print("[bold]Overall[/bold]")
    console.print(report.overall_status)
    if report.reason:
        console.print()
        console.print("[bold]Reason:[/bold]")
        console.print(report.reason)
        raise typer.Exit(code=1)


def _status_label(status: str, markup: bool = True) -> str:
    if not markup:
        return status
    if status == "OK":
        return "[green]OK[/green]"
    if status == "FAIL":
        return "[red]FAIL[/red]"
    return f"[yellow]{status}[/yellow]"


@models_app.callback()
def models(ctx: typer.Context):
    """List image model catalog entries."""
    if ctx.invoked_subcommand is not None:
        return
    _print_models(_model_catalog().list(), title="Image Model Catalog")


@models_app.command("detect")
def detect_models(
    root: str | None = typer.Option(None, "--root"),
):
    """Detect installed ComfyUI models."""
    detected = _model_catalog().detect_installed(root)
    _print_models(detected, title="Detected Image Models")


@models_app.command("search")
def search_models(query: str = typer.Argument(..., metavar="QUERY")):
    """Search image model catalog."""
    _print_models(_model_catalog().search(query), title=f"Image Models: {query}")


def _print_models(models, title: str) -> None:
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Family")
    table.add_column("Installed")
    table.add_column("Tags")
    for model in models:
        table.add_row(
            model.id,
            model.name,
            model.type,
            model.family,
            "yes" if model.installed else "no",
            ", ".join(model.tags),
        )
    console.print(table)


def _progress_table(state: dict[str, str]) -> Table:
    table = Table(title="Image Generation")
    table.add_column("Provider")
    table.add_column("Workflow")
    table.add_column("Model Family")
    table.add_column("Seed")
    table.add_column("Progress")
    table.add_column("Elapsed")
    table.add_row(
        state.get("provider", ""),
        state.get("workflow", "") or "-",
        state.get("model_family", "") or "-",
        state.get("seed", "") or "auto",
        state.get("progress", ""),
        state.get("elapsed", ""),
    )
    return table


def _print_generation_result(result) -> None:
    images = result.images or result.image_paths
    image_table = Table(title="Images")
    image_table.add_column("#")
    image_table.add_column("Path")
    for index, path in enumerate(images, start=1):
        image_table.add_row(str(index), str(path))
    console.print(image_table)

    artifact_table = Table(title="Artifacts")
    artifact_table.add_column("#")
    artifact_table.add_column("Type")
    artifact_table.add_column("Path")
    artifacts = result.artifacts or result.metadata.get("project_artifacts", [])
    for index, artifact in enumerate(artifacts, start=1):
        artifact_table.add_row(
            str(index),
            str(artifact.get("type", "image.generated")),
            str(artifact.get("path") or artifact.get("output_path") or ""),
        )
    console.print(artifact_table)

    timing_table = Table(title="Generation Time")
    timing_table.add_column("Seconds")
    timing_table.add_column("Provider")
    timing_table.add_column("Workflow")
    timing_table.add_column("Seed")
    timing_table.add_row(
        f"{result.generation_time:.3f}",
        result.provider,
        result.workflow or "-",
        str(result.seed) if result.seed is not None else "-",
    )
    console.print(timing_table)


def _runtime():
    return AegisCore().image_generation


def _model_catalog() -> ImageModelCatalog:
    return ImageModelCatalog(core=AegisCore())


app.add_typer(models_app, name="models", help="Image model catalog commands")
