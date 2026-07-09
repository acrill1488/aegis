from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("list")
def list_scenarios():
    """List available scenarios."""
    table = Table(title="Scenarios")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Steps")
    for scenario in AegisCore().scenario_runtime.scenarios.list():
        table.add_row(scenario.id, scenario.name, str(len(scenario.steps)))
    console.print(table)


@app.command("show")
def show_scenario(scenario_id: str = typer.Argument(..., metavar="SCENARIO_ID")):
    """Show a scenario definition."""
    scenario = AegisCore().scenario_runtime.scenarios.get(scenario_id)
    if scenario is None:
        console.print(f"[red]Scenario not found: {scenario_id}[/red]")
        raise typer.Exit(code=1)
    console.print(JSON.from_data(to_plain(scenario)))


@app.command("run")
def run_scenario(scenario_id: str = typer.Argument(..., metavar="SCENARIO_ID")):
    """Run a scenario through the daemon-backed runtime."""
    runtime = AegisCore().scenario_runtime
    try:
        result = runtime.run(scenario_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(JSON.from_data(to_plain(result)))
    if not result.success:
        raise typer.Exit(code=1)
