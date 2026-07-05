from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from .status import TaskStatus, TaskPriority

@dataclass
class TaskStep:
    id: int
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    tool: Optional[str] = None
    result: Optional[str] = None

@dataclass
class AegisTask:
    id: str
    title: str
    goal: str
    created_at: datetime
    updated_at: datetime
    status: TaskStatus
    priority: TaskPriority
    session_id: Optional[str] = None
    parent_id: Optional[str] = None
    steps: List[TaskStep] = field(default_factory=list)
    progress: int = 0
    result: Optional[str] = None
    metadata: Dict = field(default_factory=dict)