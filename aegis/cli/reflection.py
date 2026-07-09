from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("analyze")
def analyze(mission_id: str | None = typer.Argument(None, metavar="MISSION_ID")):
    """Analyze a completed or failed mission and create a reflection report."""
    runtime = AegisCore().reflection_engine
    try:
        report = runtime.analyze_mission(mission_id)
    except (KeyError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(report))


@app.command("latest")
def latest():
    """Show the latest reflection report."""
    report = AegisCore().reflection_engine.latest()
    if report is None:
        console.print("[yellow]No reflection reports found[/yellow]")
        return
    console.print_json(data=to_plain(report))


@app.command("reports")
def reports(limit: int = typer.Option(20, "--limit", "-n")):
    """List reflection reports."""
    rows = AegisCore().reflection_engine.list_reports(limit=limit)
    table = Table(title="Reflection Reports")
    table.add_column("Created")
    table.add_column("Mission")
    table.add_column("Success")
    table.add_column("Recovery")
    table.add_column("Recommendations")
    table.add_column("Summary")
    for report in rows:
        table.add_row(
            str(report.created_at),
            report.mission_id,
            "yes" if report.success else "no",
            str(report.recovery_count),
            str(len(report.recommendations)),
            report.summary,
        )
    console.print(table)


@app.command("recommendations")
def recommendations(status: str | None = typer.Option(None, "--status", "-s")):
    """List reflection recommendations."""
    rows = AegisCore().reflection_engine.list_recommendations(status=status)
    table = Table(title="Reflection Recommendations")
    table.add_column("Created")
    table.add_column("Type")
    table.add_column("Target")
    table.add_column("Priority")
    table.add_column("Confidence")
    table.add_column("Status")
    table.add_column("Reason")
    for recommendation in rows:
        table.add_row(
            str(recommendation.created_at),
            recommendation.type,
            recommendation.target,
            recommendation.priority,
            f"{recommendation.confidence:.2f}",
            recommendation.status,
            recommendation.reason,
        )
    console.print(table)


@app.command("stats")
def stats():
    """Show Reflection Engine statistics."""
    console.print(JSON.from_data(to_plain(AegisCore().reflection_engine.stats())))
