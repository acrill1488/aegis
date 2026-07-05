import typer
from rich.console import Console

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()

@app.command()
def execute(task_id: str, dry_run: bool = True):
    """Execute a task using the execution engine."""
    core = AegisCore()
    
    if not dry_run:
        console.print("Real execution is not implemented yet.")
        return
    
    # Execute in dry-run mode
    core.executor.execute_task(task_id)
    console.print(f"Executed task {task_id}")
