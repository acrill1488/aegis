"""Commands for inspecting and diagnosing centralized service configuration."""

from __future__ import annotations

import socket
from urllib.parse import urlparse

import httpx
import typer
from rich.console import Console
from rich.table import Table

from aegis.config.services import (
    load_services_config,
    resolve_configured_path,
    resolve_service_base_url,
)

app = typer.Typer()
console = Console()
SERVICE_LABELS = {"ollama": "Ollama", "unlimited_ocr": "Unlimited OCR", "comfyui": "ComfyUI"}
HEALTH_PATHS = {"ollama": "/api/tags", "unlimited_ocr": "/health", "comfyui": "/system_stats"}


@app.command("show")
def show() -> None:
    """Show effective service addresses and the source of each value."""
    config = load_services_config()
    console.print(f"Configuration file: {config.path}")
    console.print(f"Configuration source: {config.configuration_source}")
    table = Table(title="AEGIS Services")
    table.add_column("Service")
    table.add_column("URL")
    table.add_column("Source")
    for name, label in SERVICE_LABELS.items():
        resolved = resolve_service_base_url(name)
        table.add_row(label, resolved.value, resolved.source)
    console.print(table)
    path = resolve_configured_path("comfyui_models")
    console.print(f"ComfyUI models: {path.value} ({path.source})")


@app.command("doctor")
def doctor() -> None:
    """Validate configuration and independently probe every service."""
    config = load_services_config()
    console.print(f"Configuration: valid ({config.path})")
    table = Table(title="AEGIS Service Diagnostics")
    for heading in ("Service", "DNS", "TCP", "HTTP", "Source"):
        table.add_column(heading)
    failed = False
    for name, label in SERVICE_LABELS.items():
        resolved = resolve_service_base_url(name)
        parsed = urlparse(resolved.value)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            socket.getaddrinfo(host, port)
            dns = "OK"
        except OSError as exc:
            dns = f"ERROR: {exc}"
            failed = True
        try:
            with socket.create_connection((host, port), timeout=2):
                tcp = "OK"
        except OSError as exc:
            tcp = f"ERROR: {exc}"
            failed = True
        try:
            response = httpx.get(
                f"{resolved.value}{HEALTH_PATHS[name]}", timeout=5, trust_env=False
            )
            http = f"HTTP {response.status_code}"
            failed = failed or response.status_code >= 400
        except Exception as exc:
            http = f"ERROR: {exc}"
            failed = True
        table.add_row(label, dns, tcp, http, resolved.source)
    console.print(table)
    if failed:
        raise typer.Exit(code=1)
