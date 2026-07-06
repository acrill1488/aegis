import subprocess
from aegis.tools.base import BaseTool
from aegis.tools.result import ToolResult


class GitTool(BaseTool):
    """Tool for Git operations."""
    
    name = "git"
    description = "Tool for Git operations"
    
    def is_available(self) -> bool:
        """Check if Git is available."""
        try:
            subprocess.run(["git", "--version"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute a Git action."""
        try:
            if action == "status":
                path = kwargs.get("path")
                if not path:
                    return ToolResult(
                        success=False,
                        tool="git",
                        action=action,
                        stderr="Path is required"
                    )
                
                if not self.is_available():
                    return ToolResult(
                        success=False,
                        tool="git",
                        action=action,
                        stderr="Git is not available"
                    )
                
                try:
                    result = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )
                    return ToolResult(
                        success=True,
                        tool="git",
                        action=action,
                        stdout=result.stdout.strip()
                    )
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    return ToolResult(
                        success=False,
                        tool="git",
                        action=action,
                        stderr=str(e)
                    )
            
            else:
                return ToolResult(
                    success=False,
                    tool="git",
                    action=action,
                    stderr=f"Unknown action: {action}"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                tool="git",
                action=action,
                stderr=str(e)
            )
