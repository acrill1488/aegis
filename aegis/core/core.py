from aegis.runtime.manager import RuntimeManager
from aegis.workspace.manager import WorkspaceManager
from .registry import ServiceRegistry
from aegis.tools.registry import ToolRegistry
from aegis.tools.filesystem import FilesystemTool
from aegis.tools.git import GitTool
from aegis.tools.powershell import PowerShellTool
from aegis.session.manager import SessionManager
from aegis.task.manager import TaskManager


class AegisCore:
    def __init__(self):
        self.runtime = RuntimeManager()
        self.workspace = WorkspaceManager()
        self.sessions = SessionManager()
        self.tasks = TaskManager()
        self.registry = ServiceRegistry()
        self.tools = ToolRegistry()
        
        # Register services
        self.registry.register("runtime", self.runtime)
        self.registry.register("workspace", self.workspace)
        self.registry.register("sessions", self.sessions)
        self.registry.register("tasks", self.tasks)
        
        # Register tools
        self.tools.register(FilesystemTool())
        self.tools.register(GitTool())
        self.tools.register(PowerShellTool())
        
        # Initialize agent kernel
        from aegis.agent.kernel import AgentKernel
        self.agent = AgentKernel(self)

    def health(self) -> dict:
        """Returns the health status of the core system."""
        return {
            "runtime_available": self.runtime.is_available(),
            "models": self.runtime.list_models(),
            "workspace_root": str(self.workspace.root()),
            "workspace_projects": self.workspace.list_projects()
        }
