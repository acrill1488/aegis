import os
from aegis.tools.base import BaseTool


class FilesystemTool(BaseTool):
    """Tool for file system operations."""
    
    name = "filesystem"
    description = "Tool for file system operations"
    
    def is_available(self) -> bool:
        """Check if the filesystem tool is available."""
        return True
    
    def exists(self, path: str) -> bool:
        """Check if a path exists."""
        return os.path.exists(path)
    
    def list_dir(self, path: str) -> list[str]:
        """List contents of a directory."""
        try:
            return os.listdir(path)
        except (OSError, FileNotFoundError):
            return []
    
    def read_text(self, path: str) -> str:
        """Read text from a file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except (OSError, FileNotFoundError):
            return ""
    
    def write_text(self, path: str, content: str) -> None:
        """Write text to a file."""
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)