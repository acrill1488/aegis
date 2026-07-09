import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.capabilities import CapabilityInvocationRequest
from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("list")
def list_capabilities():
    """List registered capabilities."""
    core = AegisCore()
    table = Table(title="AEGIS Capabilities")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Owner Agent")
    table.add_column("Scope")
    table.add_column("Permissions")
    table.add_column("Tags")

    for descriptor in core.capability_runtime.list():
        table.add_row(
            descriptor.id,
            descriptor.name,
            descriptor.version,
            descriptor.owner_agent or "-",
            descriptor.machine_scope,
            ", ".join(descriptor.permissions) or "-",
            ", ".join(descriptor.tags) or "-",
        )

    console.print(table)


@app.command("show")
def show_capability(
    capability_id: str = typer.Argument(..., metavar="CAPABILITY_ID"),
):
    """Show capability descriptor and selected route."""
    core = AegisCore()
    record = core.capability_runtime.registry.resolve(capability_id)
    if record is None:
        console.print(f"[red]Capability not found:[/red] {capability_id}")
        raise typer.Exit(code=1)

    payload = {
        "descriptor": record["descriptor"],
        "providers": record["provider_handles"],
        "selected_route": core.capability_runtime.resolve(capability_id),
    }
    console.print_json(data=to_plain(payload))


@app.command("invoke")
def invoke_capability(
    capability_id: str = typer.Argument(..., metavar="CAPABILITY_ID"),
    payload_json: str = typer.Option("{}", "--payload-json"),
    payload_file: Path | None = typer.Option(None, "--payload-file"),
):
    """Invoke a capability through Capability Runtime."""
    payload = _load_payload(payload_json=payload_json, payload_file=payload_file)
    core = AegisCore()
    result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id=capability_id,
            payload=payload,
            caller="cli",
        )
    )
    console.print_json(data=to_plain(result))
    if not result.success:
        raise typer.Exit(code=1)


def _load_payload(payload_json: str, payload_file: Path | None) -> dict:
    if payload_file is not None:
        try:
            payload_text = payload_file.read_text(encoding="utf-8-sig")
        except OSError as exc:
            console.print(f"[red]Cannot read --payload-file:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        return _parse_payload(payload_text, source=f"--payload-file {payload_file}")

    return _parse_payload(payload_json, source="--payload-json")


def _parse_payload(payload_json: str, source: str) -> dict:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON in {source}:[/red] {exc.msg}")
        console.print(f"[yellow]Location:[/yellow] line {exc.lineno}, column {exc.colno}")
        raise typer.Exit(code=1) from exc

    if not isinstance(payload, dict):
        console.print(f"[red]Payload from {source} must be a JSON object.[/red]")
        raise typer.Exit(code=1)
    return payload
