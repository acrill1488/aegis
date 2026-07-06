"""CLI commands for Knowledge Engine."""

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore

app = typer.Typer()
console = Console()


@app.command("gather")
def gather(query: str = typer.Argument(...)):
    """Gather knowledge sources for a query."""
    core = AegisCore()
    bundle = core.knowledge.gather(query)

    if not bundle.sources:
        console.print("[yellow]No knowledge sources found.[/yellow]")
        return

    table = Table(title="Knowledge Sources")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Score")
    table.add_column("Preview")

    for source in bundle.sources:
        preview = source.content[:120] + ("..." if len(source.content) > 120 else "")
        table.add_row(source.type, source.title, f"{source.score:.2f}", preview)

    console.print(table)
    if bundle.summary:
        console.print("\n[bold]Summary:[/bold]")
        console.print(bundle.summary)
    if bundle.gaps:
        console.print("\n[bold yellow]Gaps:[/bold yellow]")
        for gap in bundle.gaps:
            console.print(f"- {gap}")


@app.command("context")
def context(query: str = typer.Argument(...)):
    """Build prompt-ready knowledge context for a query."""
    core = AegisCore()
    knowledge_context = core.knowledge.build_context(query)
    if not knowledge_context:
        console.print("[yellow]No knowledge context found.[/yellow]")
        return
    console.print(knowledge_context, markup=False)
