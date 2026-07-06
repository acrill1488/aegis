"""CLI commands for Skill Framework."""

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()


@app.command("list")
def list_skills():
    """List registered skills."""
    core = AegisCore()
    table = Table(title="AEGIS Skills")
    table.add_column("Name")
    table.add_column("Enabled")
    table.add_column("Capabilities")
    table.add_column("Description")

    for skill in core.skills.list():
        table.add_row(
            skill.name,
            "yes" if getattr(skill, "enabled", True) else "no",
            ", ".join(skill.capabilities),
            skill.description,
        )

    console.print(table)


@app.command("detect")
def detect_skill(prompt: str = typer.Argument(...)):
    """Detect the first skill that can handle a prompt."""
    core = AegisCore()
    skill = core.skills.detect(prompt)
    if not skill:
        console.print("[yellow]No skill detected.[/yellow]")
        return
    console.print(skill.name)


@app.command("run")
def run_skill(
    skill_name: str = typer.Argument(...),
    prompt: str = typer.Argument(...),
):
    """Run a skill by name."""
    core = AegisCore()
    skill = core.skills.get(skill_name)
    if not skill:
        console.print(f"[bold red]Skill not found:[/bold red] {skill_name}")
        raise typer.Exit(code=1)
    if not getattr(skill, "enabled", True):
        console.print(f"[bold red]Skill is disabled:[/bold red] {skill_name}")
        raise typer.Exit(code=1)

    result = skill.execute(prompt)
    if not result.success:
        console.print(f"[bold red]Skill failed:[/bold red] {result.output}")
        raise typer.Exit(code=1)
    console.print(result.output, markup=False)
