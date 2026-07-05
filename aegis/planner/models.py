from dataclasses import dataclass
from typing import Optional, List

@dataclass
class PlanStep:
    id: int
    title: str
    description: str
    tool: Optional[str] = None
    status: str = "pending"

@dataclass
class ExecutionPlan:
    task_id: str
    goal: str
    steps: List[PlanStep]
    raw_response: Optional[str] = None