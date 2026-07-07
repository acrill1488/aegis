from dataclasses import dataclass
from datetime import datetime


@dataclass
class AegisEvent:
    id: str
    type: str
    source: str
    payload: dict
    created_at: datetime
    trace_id: str | None = None


@dataclass
class EventReceipt:
    event_id: str
    delivered: int
    failed: int
