from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON

from aegis.ipc import IPCClient, IPCConnectionError
from aegis.serialization import to_plain

app = typer.Typer()
console = Console()

DEFAULT_DAEMON_IPC_HOST = "127.0.0.1"
DEFAULT_DAEMON_IPC_PORT = 8787
DAEMON_NOT_RUNNING = "AEGIS daemon is not running. Start it with: aegis daemon serve"


@app.command("serve")
def serve(
    host: str = typer.Option(DEFAULT_DAEMON_IPC_HOST, "--host"),
    port: int = typer.Option(DEFAULT_DAEMON_IPC_PORT, "--port"),
    headless: bool = typer.Option(False, "--headless/--headed"),
):
    """Show how to run Browser Service through the AEGIS daemon."""
    console.print(
        "Browser Service now runs inside the AEGIS daemon. "
        f"Start it with: aegis daemon serve --host {host} --port {port}"
    )
    if headless:
        console.print("For headless browser mode: aegis daemon serve --headless-browser")


@app.command("status")
def status():
    """Show Browser Service status."""
    _print_result(_health())


@app.command("open")
def open_browser(
    url: str = typer.Argument(..., metavar="URL"),
    headless: bool = typer.Option(False, "--headless/--headed"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Open a URL in Firefox through Browser Service."""
    _print_result(
        _invoke("open", {"url": url, "headless": headless}, oneshot, "browser.open")
    )


@app.command("navigate")
def navigate(
    url: str = typer.Argument(..., metavar="URL"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Navigate the active Firefox page."""
    _print_result(_invoke("navigate", {"url": url}, oneshot, "browser.navigate"))


@app.command("click")
def click(
    selector: str = typer.Argument(..., metavar="SELECTOR"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Click an element on the active Firefox page."""
    _print_result(_invoke("click", {"selector": selector}, oneshot, "browser.click"))


@app.command("fill")
def fill(
    selector: str = typer.Argument(..., metavar="SELECTOR"),
    value: str = typer.Argument(..., metavar="VALUE"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Fill an element on the active Firefox page."""
    _print_result(
        _invoke("fill", {"selector": selector, "value": value}, oneshot, "browser.fill")
    )


@app.command("press")
def press(
    key: str = typer.Argument(..., metavar="KEY"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Press a key on the active Firefox page."""
    _print_result(_invoke("press", {"key": key}, oneshot, "browser.press"))


@app.command("wait")
def wait(
    selector: str | None = typer.Argument(None, metavar="SELECTOR"),
    timeout_ms: int = typer.Option(30000, "--timeout-ms", "-t"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Wait for an element or timeout on the active Firefox page."""
    payload = {"timeout_ms": timeout_ms}
    if selector is not None:
        payload["selector"] = selector
    _print_result(_invoke("wait", payload, oneshot, "browser.wait"))


@app.command("select")
def select(
    selector: str = typer.Argument(..., metavar="SELECTOR"),
    value: str = typer.Argument(..., metavar="VALUE"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Select an option on the active Firefox page."""
    _print_result(
        _invoke("select", {"selector": selector, "value": value}, oneshot, "browser.select")
    )


@app.command("text")
def text(oneshot: bool = typer.Option(False, "--oneshot")):
    """Extract text from the active Firefox page."""
    _print_result(_invoke("text", {}, oneshot, "browser.extract.text"))


@app.command("inspect")
def inspect(oneshot: bool = typer.Option(False, "--oneshot")):
    """Inspect DOM controls and page structure."""
    _print_result(_invoke("inspect", {}, oneshot, "browser.inspect"))


@app.command("find")
def find(
    text: str | None = typer.Option(None, "--text"),
    placeholder: str | None = typer.Option(None, "--placeholder"),
    role: str | None = typer.Option(None, "--role"),
    name: str | None = typer.Option(None, "--name"),
    tag: str | None = typer.Option(None, "--tag"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Find DOM elements by semantic attributes."""
    payload = {
        key: value
        for key, value in {
            "text": text,
            "placeholder": placeholder,
            "role": role,
            "name": name,
            "tag": tag,
        }.items()
        if value not in (None, "")
    }
    if not payload:
        console.print("[red]find requires at least one search option[/red]")
        raise typer.Exit(code=1)
    _print_result(_invoke("find", payload, oneshot, "browser.find"))


@app.command("elements")
def elements(
    limit: int = typer.Option(50, "--limit", "-l"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """List DOM elements discovered on the active page."""
    _print_result(_invoke("elements", {"limit": limit}, oneshot, "browser.elements"))


@app.command("forms")
def forms(oneshot: bool = typer.Option(False, "--oneshot")):
    """List forms and form fields on the active page."""
    _print_result(_invoke("forms", {}, oneshot, "browser.forms"))


@app.command("screenshot")
def screenshot(
    path: Path | None = typer.Option(None, "--path", "-p"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Save a screenshot of the active Firefox page."""
    payload = {"path": str(path)} if path is not None else {}
    _print_result(_invoke("screenshot", payload, oneshot, "browser.screenshot"))


@app.command("tabs")
def tabs(oneshot: bool = typer.Option(False, "--oneshot")):
    """List tabs in the active Firefox browser."""
    _print_result(_invoke("tabs", {}, oneshot, "browser.tabs.list"))


@app.command("switch")
def switch(
    index: int = typer.Argument(..., metavar="INDEX"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Switch the active Firefox tab."""
    _print_result(_invoke("switch_tab", {"index": index}, oneshot, "browser.tabs.switch"))


@app.command("close-tab")
def close_tab(
    index: int | None = typer.Argument(None, metavar="INDEX"),
    oneshot: bool = typer.Option(False, "--oneshot"),
):
    """Close a Firefox tab."""
    payload = {"index": index} if index is not None else {}
    _print_result(_invoke("close_tab", payload, oneshot, "browser.tabs.close"))


@app.command("close")
def close(oneshot: bool = typer.Option(False, "--oneshot")):
    """Close the active Firefox browser."""
    _print_result(_invoke("close", {}, oneshot, "browser.close"))


def _health() -> dict:
    try:
        output = IPCClient().request("browser", "status")
        return output if isinstance(output, dict) else {"result": output}
    except IPCConnectionError as exc:
        _print_browser_error(str(exc))
        raise typer.Exit(code=1) from exc


def _invoke(
    action: str,
    payload: dict,
    oneshot: bool = False,
    capability_id: str | None = None,
):
    try:
        output = IPCClient().request("browser", action, payload)
        return output if isinstance(output, dict) else {"result": output}
    except IPCConnectionError as exc:
        _print_browser_error(str(exc))
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        _print_browser_error(str(exc))
        raise typer.Exit(code=1) from exc


def _print_result(data: dict) -> None:
    console.print(JSON.from_data(to_plain(data)))


def _print_browser_error(error: str) -> None:
    if "AEGIS daemon is not running" not in error and DAEMON_NOT_RUNNING in error:
        error = DAEMON_NOT_RUNNING
    console.print(f"[red]{error}[/red]")
    if "playwright install firefox" in error:
        console.print("[yellow]Run:[/yellow] python -m playwright install firefox")
