from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

@dataclass
class MemoryRecord:
    """Memory record model for AEGIS."""
    
    id: str
    created_at: datetime
    type: str
    title: str
    content: str
    tags: List[str]
    metadata: Dict