from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict


@dataclass
class AegisSession:
    id: str
    created_at: datetime
    workspace: Optional[str] = None
    role: str = "assistant"
    capability: str = "general"
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}