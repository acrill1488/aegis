from typing import Dict, Any
from aegis.tools.base import BaseTool


class ToolRegistry:
    """Registry for managing tools in AEGIS."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool in the registry."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> BaseTool:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def status(self) -> list[dict[str, Any]]:
        """Get status of all tools."""
        result = []
        for tool_name, tool in self._tools.items():
            result.append({
                "name": tool.name,
                "description": tool.description,
                "available": tool.is_available()
            })
        return result
