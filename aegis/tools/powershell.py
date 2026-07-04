import subprocess
import os
from aegis.tools.base import BaseTool


class PowerShellTool(BaseTool):
    """Tool for PowerShell operations."""
    
    name = "powershell"
    description = "Tool for PowerShell operations"
    
    def is_available(self) -> bool:
        """Check if PowerShell is available."""
        try:
            subprocess.run(["powershell", "-Command", "$null"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def run(self, command: str, cwd: str | None = None) -> dict[str, Any]:
        """Run a PowerShell command."""
        if not self.is_available():
            raise RuntimeError("PowerShell is not available")
        
        try:
            result = subprocess.run(
                ["powershell", "-Command", command],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }
        except subprocess.CalledProcessError as e:
            return {
                "returncode": e.returncode,
                "stdout": e.stdout.strip() if e.stdout else "",
                "stderr": e.stderr.strip() if e.stderr else ""
            }
        except FileNotFoundError:
            raise RuntimeError("PowerShell is not available")