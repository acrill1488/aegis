import typer
from rich.console import Console
from rich.table import Table

from aegis.memory.manager import MemoryManager

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
    manager = MemoryManager()
    record = manager.add(
        type=type,
        title=title,
        content=content,
        tags=list(tag),
    )
    console.print(f"[green]Added memory record:[/green] {record.id}")


@app.command("list")
def list_records():
    """List all memory records."""
    manager = MemoryManager()
    records = manager.list()

    if not records:
        console.print("[yellow]No memory records found.[/yellow]")
        return

    table = Table(title="Memory Records")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Tags")

    for record in records:
        table.add_row(
            record.id,
            record.title,
            record.type,
            ", ".join(record.tags),
        )

    console.print(table)


@app.command()
def search(query: str):
    """Search memory records."""
    manager = MemoryManager()
    records = manager.search(query)

    if not records:
        console.print("[yellow]No matching memory records found.[/yellow]")
        return

    table = Table(title="Memory Search Results")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Preview")

    for record in records:
        preview = record.content[:120] + ("..." if len(record.content) > 120 else "")
        table.add_row(record.id, record.title, record.type, preview)

    console.print(table)
    console.print("[yellow]Use: aegis memory show <ID> to view full content.[/yellow]")


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
