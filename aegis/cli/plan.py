import typer
from rich.console import Console
from rich.table import Table
from aegis.core.core import AegisCore
from aegis.task.status import TaskStatus

app = typer.Typer()
console = Console()

@app.command()
def create(
    task_id: str = typer.Argument(...),
    capability: str = typer.Option("coding", "--capability", "-c")
):
    """Create execution plan for a task."""
    core = AegisCore()
    plan = core.planner.create_plan(task_id, capability)
    
    console.print(f"[bold blue]Plan created for task {task_id}[/bold blue]")
    
    # Display steps in a table
    table = Table(title="Execution Plan Steps")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="magenta")
    table.add_column("Description", style="green")
    table.add_column("Tool", style="yellow")
    
    for step in plan.steps:
        table.add_row(str(step.id), step.title, step.description, str(step.tool))
    
    console.print(table)

@app.command()
def show(task_id: str = typer.Argument(...)):
    """Show saved execution plan for a task."""
    core = AegisCore()
    task = core.tasks.get(task_id)
    
    if not task.steps:
        console.print(f"[bold red]No steps found for task {task_id}[/bold red]")
        return
    
    console.print(f"[bold blue]Execution Plan for Task {task_id}[/bold blue]")
    
    # Display steps in a table
    table = Table(title="Execution Plan Steps")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="magenta")
    table.add_column("Description", style="green")
    table.add_column("Tool", style="yellow")
    table.add_column("Status", style="blue")
    
    for step in task.steps:
        table.add_row(str(step.id), step.title, step.description, str(step.tool), step.status.value)
    
    console.print(table)

if __name__ == "__main__":
    app()
