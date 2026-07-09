from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("queue")
def queue(status: str | None = typer.Option(None, "--status", "-s")):
    """List Orchestrator jobs."""
    jobs = AegisCore().orchestrator.list_jobs(status=status)
    _print_jobs(jobs)


@app.command("submit")
def submit_mission(
    mission_id: str = typer.Argument(..., metavar="MISSION_ID"),
    priority: int = typer.Option(50, "--priority", "-p"),
):
    """Submit a Mission to the Orchestrator queue."""
    runtime = AegisCore().orchestrator
    try:
        job = runtime.submit_mission(mission_id, priority=priority)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(job))


@app.command("run-next")
def run_next():
    """Run the highest priority queued or ready job."""
    result = AegisCore().orchestrator.run_next()
    if result is None:
        console.print("[yellow]No queued or ready jobs[/yellow]")
        return
    console.print_json(data=to_plain(result))
    if not result.success:
        raise typer.Exit(code=1)


@app.command("run")
def run_job(job_id: str = typer.Argument(..., metavar="JOB_ID")):
    """Run a specific Orchestrator job."""
    runtime = AegisCore().orchestrator
    try:
        result = runtime.run_job(job_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(result))
    if not result.success:
        raise typer.Exit(code=1)


@app.command("status")
def job_status(job_id: str = typer.Argument(..., metavar="JOB_ID")):
    """Show Orchestrator job status."""
    runtime = AegisCore().orchestrator
    try:
        status = runtime.status(job_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(status))


@app.command("pause")
def pause_job(job_id: str = typer.Argument(..., metavar="JOB_ID")):
    """Pause an Orchestrator job."""
    _change_job("pause", job_id)


@app.command("resume")
def resume_job(job_id: str = typer.Argument(..., metavar="JOB_ID")):
    """Resume an Orchestrator job."""
    _change_job("resume", job_id)


@app.command("cancel")
def cancel_job(job_id: str = typer.Argument(..., metavar="JOB_ID")):
    """Cancel an Orchestrator job."""
    _change_job("cancel", job_id)


@app.command("stats")
def stats():
    """Show Orchestrator queue statistics."""
    console.print_json(data=to_plain(AegisCore().orchestrator.stats()))


def print_queue_alias() -> None:
    jobs = AegisCore().orchestrator.list_jobs()
    _print_jobs(jobs)


def _change_job(action: str, job_id: str) -> None:
    runtime = AegisCore().orchestrator
    method = getattr(runtime, action)
    try:
        job = method(job_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print_json(data=to_plain(job))


def _print_jobs(jobs) -> None:
    table = Table(title="Orchestrator Queue")
    table.add_column("Job")
    table.add_column("Mission")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Worker")
    table.add_column("Goal")
    for job in jobs:
        table.add_row(
            job.id,
            job.mission_id,
            job.status,
            str(job.priority),
            job.worker_id or "",
            job.goal,
        )
    console.print(table)
