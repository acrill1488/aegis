import subprocess
from aegis.tools.base import BaseTool


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
    
    def status(self, path: str) -> str:
        """Get Git status of a repository."""
        if not self.is_available():
            return "Git is not available"
        
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "Unable to get Git status"