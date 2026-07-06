import os
from aegis.tools.base import BaseTool
from aegis.tools.result import ToolResult


class FilesystemTool(BaseTool):
    """Tool for file system operations."""
    
    name = "filesystem"
    description = "Tool for file system operations"
    
    def is_available(self) -> bool:
        """Check if the filesystem tool is available."""
        return True
    
    def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute a filesystem action."""
        try:
            if action == "exists":
                path = kwargs.get("path")
                if not path:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr="Path is required"
                    )
                exists = os.path.exists(path)
                return ToolResult(
                    success=True,
                    tool="filesystem",
                    action=action,
                    stdout=str(exists),
                    data={"exists": exists}
                )
            
            elif action == "list_dir":
                path = kwargs.get("path")
                if not path:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr="Path is required"
                    )
                try:
                    contents = os.listdir(path)
                    return ToolResult(
                        success=True,
                        tool="filesystem",
                        action=action,
                        stdout=str(contents),
                        data={"contents": contents}
                    )
                except (OSError, FileNotFoundError) as e:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr=str(e)
                    )
            
            elif action == "read_text":
                path = kwargs.get("path")
                if not path:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr="Path is required"
                    )
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return ToolResult(
                        success=True,
                        tool="filesystem",
                        action=action,
                        stdout=content
                    )
                except (OSError, FileNotFoundError) as e:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr=str(e)
                    )
            
            elif action == "write_text":
                path = kwargs.get("path")
                content = kwargs.get("content", "")
                if not path:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr="Path is required"
                    )
                
                # Validate that path is within F:\AI_WORKSPACE
                if not self._validate_path_safety(path):
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr="Path is outside of allowed workspace"
                    )
                
                try:
                    # Create parent directories if they don't exist
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return ToolResult(
                        success=True,
                        tool="filesystem",
                        action=action,
                        stdout=f"Successfully wrote to {path}"
                    )
                except Exception as e:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr=str(e)
                    )
            
            elif action == "create_dir":
                path = kwargs.get("path")
                if not path:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr="Path is required"
                    )
                
                # Validate that path is within F:\AI_WORKSPACE
                if not self._validate_path_safety(path):
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr="Path is outside of allowed workspace"
                    )
                
                try:
                    os.makedirs(path, exist_ok=True)
                    return ToolResult(
                        success=True,
                        tool="filesystem",
                        action=action,
                        stdout=f"Successfully created directory {path}"
                    )
                except Exception as e:
                    return ToolResult(
                        success=False,
                        tool="filesystem",
                        action=action,
                        stderr=str(e)
                    )
            
            else:
                return ToolResult(
                    success=False,
                    tool="filesystem",
                    action=action,
                    stderr=f"Unknown action: {action}"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                tool="filesystem",
                action=action,
                stderr=str(e)
            )
    
    def _validate_path_safety(self, path: str) -> bool:
        """Validate that the path is within F:\\AI_WORKSPACE."""
        # Normalize the path
        normalized_path = os.path.normpath(path)
        # Check if path starts with the sandbox directory
        return normalized_path.startswith(r"F:\AI_WORKSPACE")
