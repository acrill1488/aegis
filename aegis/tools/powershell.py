import subprocess
import os
from typing import Any
from aegis.tools.base import BaseTool
from aegis.tools.result import ToolResult


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
    
    def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute a PowerShell command safely."""
        if action != "run":
            return ToolResult(
                success=False,
                tool="powershell",
                action=action,
                stderr=f"Unknown action: {action}"
            )
        
        command = kwargs.get("command", "")
        cwd = kwargs.get("cwd")
        
        # List of allowed commands
        allowed_commands = {
            "python --version",
            "git status",
            "dir",
            "pytest",
            "ruff check"
        }
        
        # List of forbidden keywords
        forbidden_keywords = {
            "rm", "del", "format", "shutdown", "Remove-Item", 
            "rmdir", "erase", "remove", "delete", "clean"
        }
        
        # Check if command is in allowed list
        if command.strip() in allowed_commands:
            return self._run_command(command, cwd)
        
        # Check for forbidden keywords
        command_lower = command.lower()
        for keyword in forbidden_keywords:
            if keyword in command_lower:
                return ToolResult(
                    success=False,
                    tool="powershell",
                    action=action,
                    stderr=f"Command contains forbidden keyword: {keyword}"
                )
        
        # If command is not allowed and doesn't contain forbidden keywords, reject it
        return ToolResult(
            success=False,
            tool="powershell",
            action=action,
            stderr=f"Command not allowed: {command}"
        )
    
    def safe_run(self, command: str, cwd: str | None = None) -> dict:
        """Safely run a PowerShell command."""
        # Check if command is in allowed list
        allowed_commands = {
            "python --version",
            "git status",
            "dir",
            "pytest",
            "ruff check"
        }
        
        # List of forbidden keywords
        forbidden_keywords = {
            "rm", "del", "format", "shutdown", "Remove-Item", 
            "rmdir", "erase", "remove", "delete", "clean"
        }
        
        # Check if command is in allowed list
        if command.strip() in allowed_commands:
            return self._run_command(command, cwd)
        
        # Check for forbidden keywords
        command_lower = command.lower()
        for keyword in forbidden_keywords:
            if keyword in command_lower:
                return {
                    "success": False,
                    "tool": "powershell",
                    "action": "run",
                    "stderr": f"Command contains forbidden keyword: {keyword}",
                    "stdout": "",
                    "returncode": -1
                }
        
        # If command is not allowed and doesn't contain forbidden keywords, reject it
        return {
            "success": False,
            "tool": "powershell",
            "action": "run",
            "stderr": f"Command not allowed: {command}",
            "stdout": "",
            "returncode": -1
        }
    
    def _run_command(self, command: str, cwd: str | None = None) -> ToolResult:
        """Run a PowerShell command (internal method)."""
        if not self.is_available():
            return ToolResult(
                success=False,
                tool="powershell",
                action="run",
                stderr="PowerShell is not available"
            )
        
        try:
            result = subprocess.run(
                ["powershell", "-Command", command],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return ToolResult(
                success=True,
                tool="powershell",
                action="run",
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                exit_code=result.returncode
            )
        except subprocess.CalledProcessError as e:
            return ToolResult(
                success=False,
                tool="powershell",
                action="run",
                stdout=e.stdout.strip() if e.stdout else "",
                stderr=e.stderr.strip() if e.stderr else "",
                exit_code=e.returncode
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                tool="powershell",
                action="run",
                stderr="PowerShell is not available"
            )
