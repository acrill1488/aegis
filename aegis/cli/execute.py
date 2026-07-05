import typer
from rich.console import Console

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()

@app.command()
def execute(task_id: str):
    """Execute a task using the execution engine."""
    core = AegisCore()
    core.executor.execute_task(task_id)
    console.print(f"Executed task {task_id}")