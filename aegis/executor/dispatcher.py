from aegis.tools.filesystem import FilesystemTool
from aegis.tools.git import GitTool
from aegis.tools.powershell import PowerShellTool

class ToolDispatcher:
    def __init__(self):
        self.tools = {
            "filesystem": FilesystemTool(),
            "git": GitTool(),
            "powershell": PowerShellTool()
        }
    
    def dispatch(self, step: str):
        """Dispatch a step to the appropriate tool."""
        # For now, we'll just return a success message
        # In a real implementation, this would parse the step and route it to the correct tool
        
        # Split the step into tool name and action
        parts = step.split(":", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid step format: {step}")
        
        tool_name = parts[0]
        action = parts[1]
        
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        # Return success for now - in real implementation this would execute the actual tool
        return f"Successfully dispatched step '{step}' to tool '{tool_name}'"