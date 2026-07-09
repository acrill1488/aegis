import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from aegis.core.core import AegisCore
from aegis.memory.manager import MemoryManager
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()


@app.command()
def add(
    title: str,
    content: str = typer.Option("", "--content", "-c"),
    type: str = typer.Option("note", "--type", "-t"),
    tag: list[str] = typer.Option([], "--tag", "-T"),
):
    """Add a new memory record."""
    core = AegisCore()
    record = core.memory.add(
        type=type,
        title=title,
        content=content,
        tags=list(tag),
    )
    core.events.publish(
        event_type="memory.record_added",
        source="memory",
        payload={
            "id": record.id,
            "title": record.title,
            "type": record.type,
            "tags": record.tags,
        },
    )
    console.print(f"[green]Added memory record:[/green] {record.id}")


@app.command("list")
def list_records(
    type: str | None = typer.Option(None, "--type", "-t"),
    source: str | None = typer.Option(None, "--source", "-s"),
    limit: int = typer.Option(50, "--limit", "-n"),
):
    """List operational memory experiences."""
    records = AegisCore().operational_memory.list(
        type=type,
        source=source,
        limit=limit,
    )

    if not records:
        console.print("[yellow]No operational memory records found.[/yellow]")
        return

    table = Table(title="Operational Memory")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Source")
    table.add_column("Created")
    table.add_column("Summary")

    for record in records:
        table.add_row(
            record.id,
            record.type,
            record.source,
            record.created_at.isoformat(),
            record.summary,
        )

    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., metavar="TEXT"),
    type: str | None = typer.Option(None, "--type", "-t"),
    source: str | None = typer.Option(None, "--source", "-s"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """Search operational memory experiences."""
    records = AegisCore().operational_memory.search(
        query,
        type=type,
        source=source,
        limit=limit,
    )

    if not records:
        console.print("[yellow]No matching operational memory records found.[/yellow]")
        return

    table = Table(title="Operational Memory Search Results")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Source")
    table.add_column("Summary")

    for record in records:
        table.add_row(record.id, record.type, record.source, record.summary)

    console.print(table)


@app.command()
def stats():
    """Show operational memory statistics."""
    console.print(JSON.from_data(to_plain(AegisCore().operational_memory.stats())))


@app.command()
def clear(type: str | None = typer.Option(None, "--type", "-t")):
    """Clear operational memory records, optionally by type."""
    removed = AegisCore().operational_memory.clear(type=type)
    scope = f"type {type}" if type else "all types"
    console.print(f"[green]Removed {removed} operational memory record(s) for {scope}.[/green]")


@app.command()
def show(id: str):
    """Show a specific memory record."""
    manager = MemoryManager()
    record = manager.get(id)

    if not record:
        console.print("[red]Memory record not found.[/red]")
        return

    console.print(f"[bold]ID:[/bold] {record.id}")
    console.print(f"[bold]Title:[/bold] {record.title}")
    console.print(f"[bold]Type:[/bold] {record.type}")
    console.print(f"[bold]Created:[/bold] {record.created_at}")
    console.print(f"[bold]Tags:[/bold] {', '.join(record.tags)}")
    console.print(f"[bold]Content:[/bold]\n{record.content}")
