import typer
from rich.console import Console

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()

@app.command()
def ask(
    prompt: str = typer.Argument(...),
    capability: str = typer.Option("auto", "--capability", "-c"),
    role: str = typer.Option("assistant", "--role", "-r")
):
    """Ask a question using the brain engine."""
    core = AegisCore()
    response = core.brain.ask(prompt, capability, role)
    console.print(f"[bold blue]Response:[/bold blue] {response}")

@app.command()
def reflect(
    task_id: str = typer.Argument(...)
):
    """Reflect on a task."""
    core = AegisCore()
    reflection = core.reflection.reflect_task(task_id)
    console.print(f"[bold green]Reflection:[/bold green] {reflection}")