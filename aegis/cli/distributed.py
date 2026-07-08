from __future__ import annotations

import platform
import socket
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.distributed import MachineRecord
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("machines")
def list_machines():
    """List known distributed machines."""
    core = AegisCore()
    table = Table(title="AEGIS Distributed Machines")
    table.add_column("Machine ID")
    table.add_column("Hostname")
    table.add_column("OS")
    table.add_column("Version")
    table.add_column("Connected")
    table.add_column("Last Seen")
    table.add_column("Capabilities")

    for record in core.machine_registry.list():
        table.add_row(
            record.machine_id,
            record.hostname,
            record.os,
            record.version,
            "yes" if record.connected else "no",
            record.last_seen.isoformat() if record.last_seen else "",
            ", ".join(record.capabilities),
        )

    console.print(table)


@app.command("machine")
def show_machine(machine_id: str = typer.Argument(..., metavar="MACHINE_ID")):
    """Show one distributed machine."""
    core = AegisCore()
    record = core.machine_registry.get(machine_id)
    if record is None:
        console.print(f"[red]Machine not found: {machine_id}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(record))


@app.command("register-local")
def register_local():
    """Register the local machine as a connected development machine."""
    core = AegisCore()
    hostname = socket.gethostname()
    os_name = platform.system()
    machine_id = f"{hostname}-{os_name.lower()}" if os_name else hostname
    record = MachineRecord(
        machine_id=machine_id,
        hostname=hostname,
        os=os_name,
        version="local-dev",
        capabilities=_local_capabilities(core),
        connected=True,
        last_seen=datetime.now(),
        metadata={"registration": "local"},
    )

    registered = core.machine_registry.upsert_machine(record)
    console.print_json(data=to_plain(registered))


@app.command("disconnect")
def disconnect_machine(machine_id: str = typer.Argument(..., metavar="MACHINE_ID")):
    """Mark a distributed machine as disconnected."""
    core = AegisCore()
    try:
        record = core.machine_registry.mark_disconnected(machine_id)
    except KeyError as exc:
        console.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(record))


@app.command("capabilities")
def list_capabilities():
    """List capabilities available on connected machines."""
    core = AegisCore()
    table = Table(title="AEGIS Distributed Capabilities")
    table.add_column("Capability")
    table.add_column("Machines")

    for capability, machine_ids in core.machine_registry.list_available_capabilities().items():
        table.add_row(capability, ", ".join(machine_ids))

    console.print(table)


def _local_capabilities(core: AegisCore) -> list[str]:
    agent_runtime = getattr(core, "agent_runtime", None)
    if agent_runtime is None or not hasattr(agent_runtime, "list"):
        return []
    try:
        descriptors = agent_runtime.list()
    except Exception:
        return []

    capabilities = {
        capability.id
        for descriptor in descriptors
        for capability in getattr(descriptor, "capabilities", [])
        if getattr(capability, "id", None)
    }
    return sorted(capabilities)
