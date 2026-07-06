from aegis.tools.filesystem import FilesystemTool
from aegis.tools.git import GitTool
from aegis.tools.powershell import PowerShellTool
from aegis.tools.result import ToolResult


class ToolDispatcher:
    def __init__(self, core=None):
        self.core = core
        # Removed local tools dict - now using core.tools registry
    
    def dispatch(self, step):
        """Dispatch a step to the appropriate tool."""
        # Get tool from core.tools registry instead of local tools dict
        if self.core is None:
            raise ValueError("ToolDispatcher not initialized with AegisCore")
        
        tool = self.core.tools.get(step.tool)
        if not tool:
            raise ValueError(f"Unknown tool: {step.tool}")
        
        # Execute the tool with action and kwargs from step
        result = tool.execute(action=step.action, **step.kwargs)
        
        return result
