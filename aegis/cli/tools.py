import typer
from aegis.core.core import AegisCore
from rich.console import Console
from rich.table import Table

app = typer.Typer()

@app.command()
def status():
    """Show status of all tools."""
    core = AegisCore()
    tools_status = core.tools.status()
    
    console = Console()
    table = Table(title="Tools Status")
    table.add_column("Tool Name")
    table.add_column("Description")
    table.add_column("Available")
    
    for tool_info in tools_status:
        available = "✅" if tool_info["available"] else "❌"
        table.add_row(tool_info["name"], tool_info["description"], available)
    
    console.print(table)