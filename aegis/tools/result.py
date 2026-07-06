from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class ToolResult:
    success: bool
    tool: str
    action: str
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    data: Dict = field(default_factory=dict)