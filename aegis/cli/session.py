import typer
from rich.console import Console
from rich.table import Table
from aegis.core.core import AegisCore
from aegis.session.models import AegisSession

app = typer.Typer()
console = Console()


@app.command()
def create(
    workspace: str = typer.Option(None, "--workspace", "-w"),
    role: str = typer.Option("assistant", "--role", "-r"),
    capability: str = typer.Option("general", "--capability", "-c")
):
    """Create a new session."""
    core = AegisCore()
    session = core.sessions.create(workspace=workspace, role=role, capability=capability)
    
    console.print(f"[bold green]Created session:[/bold green] {session.id}")
    console.print(f"[bold yellow]Created at:[/bold yellow] {session.created_at}")
    if session.workspace:
        console.print(f"[bold yellow]Workspace:[/bold yellow] {session.workspace}")
    console.print(f"[bold yellow]Role:[/bold yellow] {session.role}")
    console.print(f"[bold yellow]Capability:[/bold yellow] {session.capability}")


@app.command()
def list():
    """List all sessions."""
    core = AegisCore()
    sessions = core.sessions.list_sessions()
    
    if not sessions:
        console.print("[bold yellow]No sessions found[/bold yellow]")
        return
    
    table = Table(title="Sessions")
    table.add_column("ID")
    table.add_column("Created At")
    table.add_column("Workspace")
    table.add_column("Role")
    table.add_column("Capability")
    
    for session in sessions:
        table.add_row(
            session.id,
            session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            session.workspace or "None",
            session.role,
            session.capability
        )
    
    console.print(table)


@app.command()
def active():
    """Show the active session."""
    core = AegisCore()
    active_session = core.sessions.active()
    
    if not active_session:
        console.print("[bold yellow]No active session[/bold yellow]")
        return
    
    console.print(f"[bold green]Active session:[/bold green] {active_session.id}")
    console.print(f"[bold yellow]Created at:[/bold yellow] {active_session.created_at}")
    if active_session.workspace:
        console.print(f"[bold yellow]Workspace:[/bold yellow] {active_session.workspace}")
    console.print(f"[bold yellow]Role:[/bold yellow] {active_session.role}")
    console.print(f"[bold yellow]Capability:[/bold yellow] {active_session.capability}")


@app.command()
def set_active(session_id: str):
    """Set the active session."""
    core = AegisCore()
    core.sessions.set_active(session_id)
    console.print(f"[bold green]Set active session:[/bold green] {session_id}")