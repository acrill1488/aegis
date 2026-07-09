from __future__ import annotations

from .models import OrchestratorJob, RUNNABLE_STATUSES
from .queue import OrchestratorQueue


class OrchestratorScheduler:
    """Selects local sequential jobs while keeping dependency rules explicit."""

    def __init__(self, queue: OrchestratorQueue):
        self.queue = queue

    def next_job(self) -> OrchestratorJob | None:
        jobs = self.queue.list()
        by_id = {job.id: job for job in jobs}
        candidates: list[OrchestratorJob] = []
        for job in jobs:
            if job.status not in RUNNABLE_STATUSES:
                continue
            if self._dependencies_completed(job, by_id):
                if job.status != "ready":
                    job.status = "ready"
                    self.queue.update(job)
                candidates.append(job)
            elif job.status != "waiting":
                job.status = "waiting"
                self.queue.update(job)
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (-item.priority, item.created_at, item.id))[0]

    def refresh_waiting(self) -> None:
        jobs = self.queue.list()
        by_id = {job.id: job for job in jobs}
        for job in jobs:
            if job.status != "waiting":
                continue
            if self._dependencies_completed(job, by_id):
                job.status = "ready"
                self.queue.update(job)

    def _dependencies_completed(
        self,
        job: OrchestratorJob,
        jobs: dict[str, OrchestratorJob],
    ) -> bool:
        return all(
            jobs.get(dependency_id) is not None
            and jobs[dependency_id].status == "completed"
            for dependency_id in job.dependencies
        )
