from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis.mission_engine import MissionResult
from aegis.orchestrator import ExecutionOrchestratorRuntime, OrchestratorJob, OrchestratorQueue


@dataclass
class FakeMission:
    id: str
    goal: str = "test goal"
    priority: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)


class FakeMissionRuntime:
    def __init__(self):
        self.missions = {"mission_1": FakeMission("mission_1")}
        self.ran: list[str] = []

    def show(self, mission_id: str) -> FakeMission:
        return self.missions[mission_id]

    def run(self, mission_id: str) -> MissionResult:
        self.ran.append(mission_id)
        return MissionResult(success=True, completed_nodes=["node_1"])


class FakeEventPlatform:
    def __init__(self):
        self.events: list[str] = []

    def publish(self, event_type: str, *_args, **_kwargs):
        self.events.append(event_type)


class FakeCore:
    def __init__(self):
        self.mission_runtime = FakeMissionRuntime()
        self.event_platform = FakeEventPlatform()


def test_queue_persists_jobs(tmp_path):
    queue_path = tmp_path / "queue.json"
    queue = OrchestratorQueue(queue_path)
    job = OrchestratorJob.create("mission_1", priority=75)

    queue.enqueue(job)
    loaded = OrchestratorQueue(queue_path).get(job.id)

    assert loaded is not None
    assert loaded.mission_id == "mission_1"
    assert loaded.priority == 75


def test_run_next_uses_highest_priority(tmp_path):
    core = FakeCore()
    queue = OrchestratorQueue(tmp_path / "queue.json")
    runtime = ExecutionOrchestratorRuntime(core, queue=queue)
    low = OrchestratorJob.create("mission_1", priority=10)
    high = OrchestratorJob.create("mission_1", priority=90)
    queue.enqueue(low)
    queue.enqueue(high)

    result = runtime.run_next()

    assert result is not None
    assert result.success is True
    assert queue.get(high.id).status == "completed"
    assert queue.get(low.id).status == "ready"
    assert core.mission_runtime.ran == ["mission_1"]


def test_pause_resume_cancel_update_job_status(tmp_path):
    core = FakeCore()
    queue = OrchestratorQueue(tmp_path / "queue.json")
    runtime = ExecutionOrchestratorRuntime(core, queue=queue)
    job = queue.enqueue(OrchestratorJob.create("mission_1"))

    assert runtime.pause(job.id).status == "paused"
    assert runtime.resume(job.id).status == "queued"
    assert runtime.cancel(job.id).status == "cancelled"


def test_submit_and_run_job_publish_lifecycle_events(tmp_path):
    core = FakeCore()
    runtime = ExecutionOrchestratorRuntime(core, queue=OrchestratorQueue(tmp_path / "queue.json"))

    job = runtime.submit_mission("mission_1", priority=60)
    result = runtime.run_job(job.id)

    assert result.success is True
    assert runtime.status(job.id)["status"] == "completed"
    assert core.event_platform.events == [
        "orchestrator.job.created",
        "orchestrator.job.started",
        "orchestrator.job.completed",
    ]
