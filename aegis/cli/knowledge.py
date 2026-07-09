"""CLI commands for Knowledge Engine."""

import typer
from rich.console import Console
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command("add")
def add(path: str = typer.Argument(..., metavar="PATH")):
    """Add one supported document to the local knowledge index."""
    core = AegisCore()
    document = core.knowledge.add(path)
    console.print_json(data=to_plain(document))


@app.command("scan")
def scan(path: str = typer.Argument(..., metavar="PATH")):
    """Scan a file or directory into the local knowledge index."""
    core = AegisCore()
    documents = core.knowledge.scan(path)
    console.print_json(data=to_plain(documents))


@app.command("documents")
def documents():
    """List indexed knowledge documents."""
    core = AegisCore()
    table = Table(title="Knowledge Documents")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Path")
    for document in core.knowledge.documents():
        table.add_row(document.id, document.type, document.title, document.path)
    console.print(table)


@app.command("search")
def search(query: str = typer.Argument(..., metavar="QUERY")):
    """Search local knowledge chunks."""
    core = AegisCore()
    table = Table(title="Knowledge Search")
    table.add_column("Score")
    table.add_column("Document")
    table.add_column("Chunk")
    table.add_column("Preview")
    for result in core.knowledge.search(query):
        chunk = result["chunk"]
        document = result["document"]
        preview = " ".join(chunk.text.split())
        if len(preview) > 140:
            preview = preview[:137].rstrip() + "..."
        table.add_row(
            str(result["score"]),
            document.title if document else chunk.document_id,
            str(chunk.index),
            preview,
        )
    console.print(table)


@app.command("entities")
def entities():
    """List extracted knowledge entities."""
    core = AegisCore()
    table = Table(title="Knowledge Entities")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Document")
    for entity in core.knowledge.entities():
        table.add_row(entity.type, entity.name, entity.document_id)
    console.print(table)


@app.command("show")
def show(document_id: str = typer.Argument(..., metavar="DOCUMENT_ID")):
    """Show one indexed knowledge document with chunks and entities."""
    core = AegisCore()
    try:
        value = core.knowledge.show(document_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    console.print_json(data=to_plain(value))


@app.command("stats")
def stats():
    """Show local knowledge index statistics."""
    core = AegisCore()
    console.print_json(data=to_plain(core.knowledge.stats()))


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
    knowledge_context = core.knowledge.build_prompt_context(query)
    if not knowledge_context:
        console.print("[yellow]No knowledge context found.[/yellow]")
        return
    console.print(knowledge_context, markup=False)
