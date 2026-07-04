from aegis.runtime.manager import RuntimeManager
from aegis.workspace.manager import WorkspaceManager
from .registry import ServiceRegistry


class AegisCore:
    def __init__(self):
        self.runtime = RuntimeManager()
        self.workspace = WorkspaceManager()
        self.registry = ServiceRegistry()
        
        # Register services
        self.registry.register("runtime", self.runtime)
        self.registry.register("workspace", self.workspace)

    def health(self) -> dict:
        """Returns the health status of the core system."""
        return {
            "runtime_available": self.runtime.is_available(),
            "models": self.runtime.list_models(),
            "workspace_root": str(self.workspace.root()),
            "workspace_projects": self.workspace.list_projects()
        }
