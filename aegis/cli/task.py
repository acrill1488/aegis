import typer
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.table import Table
from aegis.core.core import AegisCore
from aegis.task.models import AegisTask
from aegis.task.status import TaskStatus, TaskPriority

console = Console()
app = typer.Typer()

@app.command()
def create(
    title: str = typer.Argument(...),
    goal: str = typer.Option(..., "--goal", "-g"),
    priority: str = typer.Option("normal", "--priority", "-p", help="Task priority"),
    session_id: Optional[str] = typer.Option(None, "--session-id", "-s"),
    parent_id: Optional[str] = typer.Option(None, "--parent-id", "-P")
):
    """Create a new task."""
    core = AegisCore()
    
    # Convert priority string to enum
    priority_enum = getattr(TaskPriority, priority.upper())
    
    task = core.tasks.create(
        title=title,
        goal=goal,
        priority=priority_enum,
        session_id=session_id,
        parent_id=parent_id
    )
    
    console.print(f"[green]Created task[/green] {task.id}")
    console.print(f"Title: {task.title}")
    console.print(f"Goal: {task.goal}")
    console.print(f"Priority: {task.priority.value}")

@app.command()
def list():
    """List all tasks."""
    core = AegisCore()
    tasks = core.tasks.list_tasks()
    
    table = Table(title="Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Priority", style="yellow")
    table.add_column("Created", style="blue")
    
    for task in tasks:
        table.add_row(
            task.id,
            task.title,
            task.status.value,
            task.priority.value,
            task.created_at.strftime("%Y-%m-%d %H:%M")
        )
    
    console.print(table)

@app.command()
def show(
    task_id: str = typer.Argument(...)
):
    """Show task details."""
    core = AegisCore()
    task = core.tasks.get(task_id)
    
    if not task:
        console.print(f"[red]Task {task_id} not found[/red]")
        return
    
    console.print(f"[bold]Task:[/bold] {task.id}")
    console.print(f"[bold]Title:[/bold] {task.title}")
    console.print(f"[bold]Goal:[/bold] {task.goal}")
    console.print(f"[bold]Status:[/bold] {task.status.value}")
    console.print(f"[bold]Priority:[/bold] {task.priority.value}")
    console.print(f"[bold]Created:[/bold] {task.created_at.strftime('%Y-%m-%d %H:%M')}")
    console.print(f"[bold]Updated:[/bold] {task.updated_at.strftime('%Y-%m-%d %H:%M')}")
    
    if task.result:
        console.print(f"[bold]Result:[/bold] {task.result}")
    
    if task.steps:
        console.print("[bold]Steps:[/bold]")
        for step in task.steps:
            console.print(f"  - [{step.status.value}] {step.title}")

@app.command()
def complete(
    task_id: str = typer.Argument(...),
    result: str = typer.Option(..., "--result", "-r")
):
    """Complete a task with a result."""
    core = AegisCore()
    task = core.tasks.set_result(task_id, result)
    
    if not task:
        console.print(f"[red]Task {task_id} not found[/red]")
        return
    
    console.print(f"[green]Completed task[/green] {task.id}")
    console.print(f"Result: {result}")

@app.command()
def cancel(
    task_id: str = typer.Argument(...)
):
    """Cancel a task."""
    core = AegisCore()
    task = core.tasks.cancel(task_id)
    
    if not task:
        console.print(f"[red]Task {task_id} not found[/red]")
        return
    
    console.print(f"[yellow]Cancelled task[/yellow] {task.id}")

# Export the app as 'task' for main.py import
task = app
