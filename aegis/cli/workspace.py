import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from aegis.workspace.manager import WorkspaceManager

app = typer.Typer()
console = Console()
workspace_manager = WorkspaceManager()

@app.command()
def init():
    """Initialize workspace structure."""
    console.print(Panel("Initializing Workspace"))
    
    created_paths = workspace_manager.ensure_structure()
    
    if created_paths:
        console.print("[bold green]Created directories:[/bold green]")
        for path in created_paths:
            console.print(f"  • {path}")
    else:
        console.print("[bold yellow]Workspace structure already exists[/bold yellow]")

@app.command()
def list():
    """List all projects."""
    console.print(Panel("Projects"))
    
    projects = workspace_manager.list_projects()
    
    if not projects:
        console.print("[bold yellow]No projects found[/bold yellow]")
        return
    
    table = Table(title="Projects")
    table.add_column("Project Name")
    table.add_column("Path")
    table.add_column("Has Git")
    table.add_column("Has README")
    table.add_column("File Count")
    
    for project_name in projects:
        desc = workspace_manager.describe_project(project_name)
        # Safe path display - use relative_to only if possible, otherwise show full path
        try:
            display_path = str(Path(desc["path"]).relative_to(workspace_manager.root()))
        except ValueError:
            display_path = str(desc["path"])
            
        table.add_row(
            project_name,
            display_path,
            "✅" if desc["has_git"] else "❌",
            "✅" if desc["has_readme"] else "❌",
            str(desc["file_count"])
        )
    
    console.print(table)

@app.command()
def create(name: str):
    """Create a new project."""
    console.print(Panel(f"Creating Project: {name}"))
    
    project_path = workspace_manager.create_project(name)
    
    if project_path:
        console.print(f"[bold green]Project created at:[/bold green] {project_path}")
    else:
        console.print(f"[bold yellow]Project already exists at:[/bold yellow] {project_path}")

@app.command()
def describe(name: str):
    """Describe a project."""
    console.print(Panel(f"Project Description: {name}"))
    
    desc = workspace_manager.describe_project(name)
    
    table = Table()
    table.add_column("Property")
    table.add_column("Value")
    
    table.add_row("Name", desc["name"])
    table.add_row("Path", desc["path"])
    table.add_row("Exists", "✅" if desc["exists"] else "❌")
    table.add_row("Has Git", "✅" if desc["has_git"] else "❌")
    table.add_row("Has README", "✅" if desc["has_readme"] else "❌")
    table.add_row("File Count", str(desc["file_count"]))
    
    console.print(table)

if __name__ == "__main__":
    app()