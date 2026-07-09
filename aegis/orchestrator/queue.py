from __future__ import annotations

import json
from pathlib import Path

from .models import OrchestratorJob, TERMINAL_STATUSES, utc_now


DEFAULT_QUEUE_PATH = Path(r"F:\AI_WORKSPACE\orchestrator\queue.json")


class OrchestratorQueue:
    """Persistent queue for mission execution jobs."""

    def __init__(self, path: str | Path = DEFAULT_QUEUE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_jobs([])

    def enqueue(self, job: OrchestratorJob) -> OrchestratorJob:
        job.validate()
        jobs = self._read_jobs()
        if any(existing.id == job.id for existing in jobs):
            raise ValueError(f"Orchestrator job already exists: {job.id}")
        jobs.append(job)
        self._write_jobs(jobs)
        return job

    def dequeue(self) -> OrchestratorJob | None:
        runnable = [job for job in self.list() if job.status in {"ready", "queued"}]
        if not runnable:
            return None
        return sorted(runnable, key=lambda item: (-item.priority, item.created_at, item.id))[0]

    def list(self, status: str | None = None) -> list[OrchestratorJob]:
        jobs = self._read_jobs()
        if status is None:
            return jobs
        return [job for job in jobs if job.status == status]

    def get(self, job_id: str) -> OrchestratorJob | None:
        for job in self._read_jobs():
            if job.id == job_id:
                return job
        return None

    def update(self, job: OrchestratorJob) -> OrchestratorJob:
        job.validate()
        jobs = self._read_jobs()
        for index, existing in enumerate(jobs):
            if existing.id == job.id:
                jobs[index] = job
                self._write_jobs(jobs)
                return job
        raise KeyError(f"Orchestrator job not found: {job.id}")

    def cancel(self, job_id: str) -> OrchestratorJob:
        job = self._require(job_id)
        if job.status not in TERMINAL_STATUSES:
            job.status = "cancelled"
            job.completed_at = utc_now()
        return self.update(job)

    def pause(self, job_id: str) -> OrchestratorJob:
        job = self._require(job_id)
        if job.status not in TERMINAL_STATUSES:
            job.status = "paused"
        return self.update(job)

    def resume(self, job_id: str) -> OrchestratorJob:
        job = self._require(job_id)
        if job.status == "paused":
            job.status = "queued"
        return self.update(job)

    def _require(self, job_id: str) -> OrchestratorJob:
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Orchestrator job not found: {job_id}")
        return job

    def _read_jobs(self) -> list[OrchestratorJob]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = []
        if isinstance(raw, dict):
            raw = raw.get("jobs", [])
        if not isinstance(raw, list):
            return []
        jobs: list[OrchestratorJob] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                jobs.append(OrchestratorJob.from_dict(item))
            except (KeyError, TypeError, ValueError):
                continue
        return jobs

    def _write_jobs(self, jobs: list[OrchestratorJob]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [job.to_dict() for job in jobs]
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.path)
