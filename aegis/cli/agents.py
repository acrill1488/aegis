import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.agents.runtime import AgentInvocation
from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("list")
def list_agents():
    """List registered agents."""
    core = AegisCore()
    table = Table(title="AEGIS Agents")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Machine")
    table.add_column("Status")
    table.add_column("Health")
    table.add_column("Capabilities")

    for descriptor in core.agent_runtime.list():
        table.add_row(
            descriptor.id,
            descriptor.name,
            descriptor.version,
            descriptor.machine_id,
            descriptor.status.value,
            descriptor.health.state.value,
            ", ".join(capability.id for capability in descriptor.capabilities),
        )

    console.print(table)


@app.command("start")
def start_agent(agent_id: str = typer.Argument(..., metavar="AGENT_ID")):
    """Start an agent."""
    core = AegisCore()
    descriptor = _call(lambda: core.agent_runtime.start(agent_id))
    console.print_json(data=to_plain(descriptor))


@app.command("stop")
def stop_agent(
    agent_id: str = typer.Argument(..., metavar="AGENT_ID"),
    reason: str = typer.Option("", "--reason", "-r"),
):
    """Stop an agent."""
    core = AegisCore()
    descriptor = _call(lambda: core.agent_runtime.stop(agent_id, reason=reason))
    console.print_json(data=to_plain(descriptor))


@app.command("health")
def health_agent(agent_id: str = typer.Argument(..., metavar="AGENT_ID")):
    """Show agent health."""
    core = AegisCore()
    health = core.agent_runtime.health(agent_id)
    console.print_json(data=to_plain(health))


@app.command("invoke")
def invoke_agent(
    agent_id: str = typer.Argument(..., metavar="AGENT_ID"),
    capability_id: str = typer.Argument(..., metavar="CAPABILITY_ID"),
    payload_json: str = typer.Option("{}", "--payload-json"),
    payload_file: Path | None = typer.Option(None, "--payload-file"),
):
    """Invoke an agent capability."""
    payload = _load_payload(payload_json=payload_json, payload_file=payload_file)
    core = AegisCore()
    result = _call(
        lambda: core.agent_runtime.invoke(
            agent_id,
            AgentInvocation(capability_id=capability_id, payload=payload),
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


def _call(action):
    try:
        return action()
    except KeyError as exc:
        console.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(code=1) from exc

