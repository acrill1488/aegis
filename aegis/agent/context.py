from typing import Dict, Any


class ContextBuilder:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def build(self) -> Dict[str, Any]:
        """Build context dictionary for the agent."""
        return {
            "workspace_root": str(self.core.workspace.root()),
            "workspace_projects": self.core.workspace.list_projects(),
            "registered_services": self.core.registry.list_services(),
            "registered_tools": self.core.tools.list_tools(),
        }