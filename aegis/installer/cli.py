from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from .errors import InstallerError
from .manager import PackageManager
from .models import DiagnosticReport


console = Console()


def _manager() -> PackageManager:
    return PackageManager()


def _fail(exc: InstallerError) -> None:
    console.print(f"[red]{exc}[/red]")
    raise typer.Exit(code=1)


def install(component: str = typer.Argument(..., help="Component id from the registry")) -> None:
    """Install a component and its dependencies."""
    try:
        report = _manager().install(component)
        console.print(f"[green]Installed[/green] {report.package_id} {report.version}" if report.changed else f"[green]Already installed[/green] {report.package_id} {report.version}")
    except InstallerError as exc:
        _fail(exc)


def remove(component: str = typer.Argument(...), unused: bool = typer.Option(False, "--unused", help="Reserved for removal of unused dependencies")) -> None:
    """Remove a component without removing shared dependencies."""
    try:
        report = _manager().remove(component, {"unused": unused})
        console.print(f"[green]Removed[/green] {component}" if report.changed else f"{component} is not installed")
    except InstallerError as exc:
        _fail(exc)


def update(component: str | None = typer.Argument(None), yes: bool = typer.Option(False, "--yes", "-y", help="Explicitly approve the update")) -> None:
    """Update one or all installed components; never runs silently."""
    try:
        report = _manager().update(component, {"confirmed": yes})
        console.print_json(json.dumps(report.model_dump(), ensure_ascii=False))
        if not report.success:
            raise typer.Exit(code=1)
    except InstallerError as exc:
        _fail(exc)


def bootstrap() -> None:
    """Prepare a new machine workspace, configuration, state, and diagnostics."""
    try:
        report = _manager().bootstrap()
        _print_diagnostics(report)
        if not report.ok:
            raise typer.Exit(code=1)
    except InstallerError as exc:
        _fail(exc)


def registry() -> None:
    """Show all validated component manifests."""
    manager = _manager()
    table = Table(title="AEGIS Component Registry")
    for column in ("Id", "Name", "Type", "Version"):
        table.add_column(column)
    try:
        for item in manager.registry.list():
            table.add_row(item.id, item.name, item.type, item.version)
        console.print(table)
    except InstallerError as exc:
        _fail(exc)


def list_packages() -> None:
    """Show installed components."""
    table = Table(title="Installed")
    for column in ("Component", "Version", "Status", "Health"):
        table.add_column(column)
    try:
        for item in _manager().list():
            table.add_row(item.component, item.version, item.status, item.health)
        console.print(table)
    except InstallerError as exc:
        _fail(exc)


def search(query: str = typer.Argument("")) -> None:
    """Search available packages."""
    try:
        for item in _manager().registry.search(query):
            console.print(f"[bold]{item.name}[/bold]  {item.id}  {item.version}")
    except InstallerError as exc:
        _fail(exc)


def rollback(component: str | None = typer.Argument(None)) -> None:
    """Restore the latest recorded package state."""
    try:
        _manager().rollback(component)
        console.print("[green]Rollback completed[/green]")
    except InstallerError as exc:
        _fail(exc)


def doctor(component: str | None = typer.Argument(None)) -> None:
    """Diagnose configuration, registry, services, providers, models and workflows."""
    try:
        report = _manager().diagnose(component)
        _print_diagnostics(report)
        if not report.ok:
            raise typer.Exit(code=1)
    except InstallerError as exc:
        _fail(exc)


def _print_diagnostics(report: DiagnosticReport) -> None:
    table = Table(title="AEGIS Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    for check in report.checks:
        table.add_row(check.name, "OK" if check.ok else ("WARN" if not check.required else "FAIL"), check.details)
    console.print(table)


def register_commands(app: typer.Typer) -> None:
    app.command("install")(install)
    app.command("remove")(remove)
    app.command("update")(update)
    app.command("bootstrap")(bootstrap)
    app.command("registry")(registry)
    app.command("list")(list_packages)
    app.command("search")(search)
    app.command("rollback")(rollback)
    app.command("doctor")(doctor)
