"""CLI commands for the Retriever pipeline."""

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.retriever.pipeline import RetrieverPipeline
from aegis.retriever.providers import DEFAULT_PROVIDERS

app = typer.Typer()
console = Console()


@app.command("providers")
def providers():
    """List retriever providers."""
    table = Table(title="Retriever Providers")
    table.add_column("Name")

    for provider_cls in DEFAULT_PROVIDERS:
        table.add_row(provider_cls().name())

    console.print(table)


@app.command("retrieve")
def retrieve(query: str = typer.Argument(...)):
    """Run the retriever pipeline for a query."""
    core = AegisCore()
    result = RetrieverPipeline(core=core).retrieve(query)

    if not result.documents:
        console.print("[yellow]No documents retrieved.[/yellow]")
    else:
        table = Table(title="Retrieved Documents")
        table.add_column("Source")
        table.add_column("Title")
        table.add_column("Score")
        table.add_column("URL")

        for document in result.documents:
            table.add_row(
                document.source,
                document.title,
                f"{document.score:.2f}",
                document.url,
            )

        console.print(table)

    if result.summary:
        console.print("\n[bold]Summary:[/bold]")
        console.print(result.summary, markup=False)

    if result.gaps:
        console.print("\n[bold yellow]Gaps:[/bold yellow]")
        for gap in result.gaps:
            console.print(f"- {gap}")
