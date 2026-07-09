from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON

from aegis.capabilities import CapabilityInvocationRequest
from aegis.core.core import AegisCore
from aegis.serialization import to_plain

BROWSER_AGENT_ID = "browser-agent"

app = typer.Typer()
console = Console()


@app.command("open")
def open_browser(
    url: str = typer.Argument(..., metavar="URL"),
    headless: bool = typer.Option(False, "--headless/--headed"),
):
    """Open a URL in Firefox through BrowserAgent."""
    _print_result(_invoke("browser.open", {"url": url, "headless": headless}))


@app.command("navigate")
def navigate(url: str = typer.Argument(..., metavar="URL")):
    """Navigate the active Firefox page."""
    _print_result(_invoke("browser.navigate", {"url": url}))


@app.command("text")
def text():
    """Extract text from the active Firefox page."""
    _print_result(_invoke("browser.extract.text", {}))


@app.command("screenshot")
def screenshot(path: Path | None = typer.Option(None, "--path", "-p")):
    """Save a screenshot of the active Firefox page."""
    payload = {"path": str(path)} if path is not None else {}
    _print_result(_invoke("browser.screenshot", payload))


@app.command("close")
def close():
    """Close the active Firefox browser."""
    _print_result(_invoke("browser.close", {}))


@app.command("status")
def status():
    """Show BrowserAgent and Playwright provider status."""
    core = AegisCore()
    agent = core.agent_runtime.registry.get(BROWSER_AGENT_ID)
    if agent is None:
        console.print("[red]BrowserAgent is not registered.[/red]")
        raise typer.Exit(code=1)
    payload = {
        "agent": to_plain(agent.descriptor),
        "provider": agent.provider.status(),
    }
    console.print(JSON.from_data(payload))


def _invoke(capability_id: str, payload: dict):
    core = AegisCore()
    result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id=capability_id,
            payload=payload,
            caller="cli",
        )
    )
    if not result.success:
        _print_browser_error(result.error or "Browser invocation failed")
        raise typer.Exit(code=1)
    return result.output


def _print_result(data: dict) -> None:
    console.print(JSON.from_data(to_plain(data)))


def _print_browser_error(error: str) -> None:
    console.print(f"[red]{error}[/red]")
    if "playwright install firefox" in error:
        console.print("[yellow]Run:[/yellow] python -m playwright install firefox")
