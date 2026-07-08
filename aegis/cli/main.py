import shutil
import subprocess
import sys
import os

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

from aegis.vision.screen import capture_screen
from aegis.runtime.manager import RuntimeManager
from aegis.config.runtime_config import get_runtime_profile
from aegis.core.core import AegisCore
from aegis.tools.registry import ToolRegistry

# Import workspace commands
from .workspace import app as workspace_app

# Import session commands
from .session import app as session_app

# Import core commands
from .core import app as core_app
from .tools import app as tools_app
from .memory import app as memory_app

# Import plan commands
from .plan import app as plan_app
from .task import task as task_app
from .router import app as router_app
from .brain import app as brain_app
from .web import app as web_app
from .knowledge import app as knowledge_app
from .context import app as context_app
from .skills import app as skills_app
from .retriever import app as retriever_app
from .system import app as system_app
from .events import app as events_app
from .daemon import app as daemon_app
from .live import app as live_app
from .agents import app as agents_app
from .windows import app as windows_app
from .scheduler import app as scheduler_app
from .distributed import app as distributed_app

app = typer.Typer()
console = Console()

app.add_typer(workspace_app, name="workspace", help="Workspace management commands")
app.add_typer(session_app, name="session", help="Session management commands")
app.add_typer(core_app, name="core", help="AEGIS Core commands")
app.add_typer(tools_app, name="tools", help="Tool registry commands")
app.add_typer(plan_app, name="plan", help="Plan management commands")
app.add_typer(task_app, name="task", help="Task management commands")
app.add_typer(router_app, name="router", help="Router commands")
app.add_typer(memory_app, name="memory", help="Memory commands")
app.add_typer(brain_app, name="brain", help="Brain commands")
app.add_typer(web_app, name="web", help="Web browser commands")
app.add_typer(knowledge_app, name="knowledge", help="Knowledge Engine commands")
app.add_typer(retriever_app, name="retriever", help="Retriever pipeline commands")
app.add_typer(context_app, name="context", help="Context Builder commands")
app.add_typer(skills_app, name="skills", help="Skill Framework commands")
app.add_typer(system_app, name="system", help="System status commands")
app.add_typer(events_app, name="events", help="Event bus commands")
app.add_typer(daemon_app, name="daemon", help="AEGIS daemon commands")
app.add_typer(live_app, name="live", help="Live context commands")
app.add_typer(agents_app, name="agents", help="Agent runtime commands")
app.add_typer(windows_app, name="windows", help="Windows Agent commands")
app.add_typer(scheduler_app, name="scheduler", help="Scheduler commands")
app.add_typer(distributed_app, name="distributed", help="Distributed runtime commands")

@app.command("execute")
def execute_command(
    task_id: str,
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Run without making real changes",
    ),
):
    """Execute a task using the execution engine."""
    core = AegisCore()
    core.executor.execute_task(task_id, dry_run=dry_run)


def check_command(command: str) -> bool:
    return shutil.which(command) is not None


@app.command()
def doctor():
    console.print(Panel("AEGIS System Doctor"))

    table = Table(title="System Check Results")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row("Python Executable", "✅", sys.executable)
    table.add_row("Python Version", "✅", sys.version.split()[0])
    table.add_row("Git", "✅" if check_command("git") else "❌", "git")
    table.add_row("Node.js", "✅" if check_command("node") else "❌", "node")

    npm_ok = check_command("npm") or check_command("npm.cmd")
    table.add_row("npm", "✅" if npm_ok else "❌", "npm")

    try:
        r = httpx.get("http://192.168.1.7:11434/api/tags", timeout=30.0, trust_env=False)
        if r.status_code == 200:
            data = r.json()
            models = data.get("models", [])
            model_names = ", ".join([m.get("name", "unknown") for m in models]) or "No models"
            table.add_row("Ollama API", "✅", "Available")
            table.add_row("Ollama Models", "✅", model_names)
        elif r.status_code == 503:
            table.add_row("Ollama API", "⚠️", "Busy / loading model")
            table.add_row("Ollama Models", "⚠️", "Cannot check while busy")
        else:
            table.add_row("Ollama API", "❌", f"Status {r.status_code}")
            table.add_row("Ollama Models", "⚠️", "Cannot check models")
    except Exception as e:
        table.add_row("Ollama API", "❌", str(e))
        table.add_row("Ollama Models", "⚠️", "Cannot check models")


@app.command()
def models(profile: str = typer.Option("coding", "--profile", "-p")):
    """List available models."""
    runtime = RuntimeManager(profile_name=profile)
    try:
        # Debug information
        console.print(f"[bold yellow]Selected profile:[/bold yellow] {profile}")
        
        # Get profile details for debug info
        from ..config.runtime_config import get_runtime_profile
        profile_config = get_runtime_profile(profile)
        console.print(f"[bold yellow]Base URL:[/bold yellow] {profile_config['base_url']}")
        console.print(f"[bold yellow]Model:[/bold yellow] {profile_config['model']}")
        
        # Make direct request to get debug info about status and response
        import httpx
        url = f"{profile_config['base_url'].rstrip('/')}/api/tags"
        try:
            r = httpx.get(url, timeout=30, trust_env=False)
            console.print(f"[bold yellow]Status Code:[/bold yellow] {r.status_code}")
            response_preview = r.text[:200] + "..." if len(r.text) > 200 else r.text
            console.print(f"[bold yellow]Response preview:[/bold yellow] {response_preview}")
        except Exception as e:
            console.print(f"[bold yellow]Connection Error:[/bold yellow] {e}")
        
        models = runtime.list_models()
        if not models:
            console.print("[bold red]No models found[/bold red]")
            return
        
        table = Table(title="Available Models")
        table.add_column("Model Name")
        
        for model in models:
            table.add_row(model)
        
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error fetching models: {e}[/bold red]")

@app.command()
def chat(prompt: str = typer.Argument(...), 
         model: str = typer.Option(None, "--model", "-m"),
         profile: str = typer.Option("coding", "--profile", "-p")):
    """Chat with AI model."""
    runtime = RuntimeManager(profile_name=profile)
    try:
        if not runtime.is_available():
            console.print("[bold red]Runtime is not available[/bold red]")
            return
            
        response = runtime.chat(prompt=prompt, profile=profile, model=model, temperature=None, max_tokens=None)
        console.print(f"[bold blue]Model:[/bold blue] {model}")
        console.print(f"[bold green]Response:[/bold green] {response}")
    except Exception as e:
        console.print(f"[bold red]Error during chat: {e}[/bold red]")

@app.command()
def screen():
    """Capture screenshot of the main monitor."""
    try:
        filepath = capture_screen()
        console.print(f"Screenshot saved to: [bold green]{filepath}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error capturing screenshot:[/bold red] {e}")

import os
import sys

@app.command()
def dev_info():
    """Display development environment information."""
    console.print("[bold blue]Development Environment Info[/bold blue]")
    
    # Python executable path
    console.print(f"[bold yellow]Python executable:[/bold yellow] {sys.executable}")
    
    # Python version
    console.print(f"[bold yellow]Python version:[/bold yellow] {sys.version.split()[0]}")
    
    # Check if .venv is active
    venv_active = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    console.print(f"[bold yellow]Virtual environment active:[/bold yellow] {'Yes' if venv_active else 'No'}")
    
    # Current project path
    console.print(f"[bold yellow]Current project path:[/bold yellow] {os.getcwd()}")
    
    # Check dependencies
    try:
        import yaml
        console.print("[bold yellow]pyyaml:[/bold yellow] Installed")
    except ImportError:
        console.print("[bold yellow]pyyaml:[/bold yellow] Not installed")
        
    try:
        import httpx
        console.print("[bold yellow]httpx:[/bold yellow] Installed")
    except ImportError:
        console.print("[bold yellow]httpx:[/bold yellow] Not installed")
        
    try:
        import typer
        console.print("[bold yellow]typer:[/bold yellow] Installed")
    except ImportError:
        console.print("[bold yellow]typer:[/bold yellow] Not installed")


@app.command()
def tools_status():
    """Show status of all tools."""
    core = AegisCore()
    tools_status = core.tools.status()
    console.print(table)
    table = Table(title="Tools Status")
    table.add_column("Tool Name")
    table.add_column("Description")
    table.add_column("Available")
    
    for tool_info in tools_status:
        available = "✅" if tool_info["available"] else "❌"
        table.add_row(tool_info["name"], tool_info["description"], available)
    


@app.command()
def ask(
    prompt: str = typer.Argument(...),
    capability: str = typer.Option("auto", "--capability", "-c"),
    role: str = typer.Option("assistant", "--role", "-r")
):
    """Ask the AEGIS agent a question."""
    core = AegisCore()
    response = core.brain.ask(prompt, capability, role)
    console.print(f"[bold blue]Response:[/bold blue] {response}")


@app.command()
def version():
    console.print("AEGIS CLI 0.1.0")
if __name__ == "__main__":
    app()
