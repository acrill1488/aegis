import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()

@app.command()
def status():
    """Display AEGIS core status."""
    core = AegisCore()
    health = core.health()
    
    console.print(Panel("AEGIS Core Status"))
    
    # Display runtime information
    table = Table(title="Runtime")
    table.add_column("Property")
    table.add_column("Value")
    
    table.add_row("Available", "✅" if health["runtime_available"] else "❌")
    table.add_row("Models", ", ".join(health["models"]) if health["models"] else "No models")
    
    console.print(table)
    
    # Display workspace information
    table = Table(title="Workspace")
    table.add_column("Property")
    table.add_column("Value")
    
    table.add_row("Root", health["workspace_root"])
    table.add_row("Projects", ", ".join(health["workspace_projects"]) if health["workspace_projects"] else "No projects")
    
    console.print(table)
    
    # Display registered services
    table = Table(title="Registered Services")
    table.add_column("Service Name")
    
    services = core.registry.list_services()
    for service in services:
        table.add_row(service)
    
    console.print(table)