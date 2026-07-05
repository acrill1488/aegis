import typer
from rich.console import Console

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()

@app.command()
def execute(task_id: str, dry_run: bool = typer.Option(
    True,
    "--dry-run/--no-dry-run",
    help="Run without making real changes"
)):
    """Execute a task using the execution engine."""
    core = AegisCore()
    
    # Execute with the specified mode
    core.executor.execute_task(task_id, dry_run=dry_run)
    console.print(f"Executed task {task_id}")
