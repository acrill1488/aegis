from __future__ import annotations

from collections import Counter
from typing import Any

from aegis.mission_engine import MissionResult
from aegis.serialization import to_plain

from .models import OrchestratorJob, TERMINAL_STATUSES, utc_now
from .queue import OrchestratorQueue
from .scheduler import OrchestratorScheduler


class ExecutionOrchestratorRuntime:
    """Coordinates MissionRuntime execution through a persistent job queue."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        queue: OrchestratorQueue | None = None,
        scheduler: OrchestratorScheduler | None = None,
    ):
        self.core = core
        self.queue = queue or OrchestratorQueue()
        self.scheduler = scheduler or OrchestratorScheduler(self.queue)

    def submit_mission(self, mission_id: str, priority: int = 50) -> OrchestratorJob:
        mission = self._mission_runtime().show(mission_id)
        job = OrchestratorJob.create(
            mission_id,
            project_id=mission.metadata.get("project_id"),
            goal=mission.goal,
            priority=priority,
            metadata={
                "mission_priority": mission.priority,
                "correlation_id": mission.metadata.get("correlation_id"),
            },
        )
        self.queue.enqueue(job)
        self._publish("orchestrator.job.created", job, payload={"priority": priority})
        return job

    def run_next(self) -> MissionResult | None:
        self.scheduler.refresh_waiting()
        job = self.scheduler.next_job()
        if job is None:
            return None
        return self.run_job(job.id)

    def run_job(self, job_id: str) -> MissionResult:
        job = self._require_job(job_id)
        if job.status == "cancelled":
            return self._skipped_result(job, "Job is cancelled")
        if job.status == "paused":
            return self._skipped_result(job, "Job is paused")
        if job.status in {"completed", "failed"}:
            return self._skipped_result(job, f"Job is already {job.status}")

        job.status = "running"
        job.started_at = job.started_at or utc_now()
        job.worker_id = "local"
        self.queue.update(job)
        self._publish("orchestrator.job.started", job)

        try:
            result = self._mission_runtime().run(job.mission_id)
        except Exception as exc:
            job.status = "failed"
            job.completed_at = utc_now()
            job.metadata["error"] = str(exc)
            self.queue.update(job)
            self._publish(
                "orchestrator.job.failed",
                job,
                payload={"error": str(exc)},
                severity="error",
            )
            raise

        job.completed_at = utc_now()
        job.metadata["mission_result"] = to_plain(result)
        if result.success:
            job.status = "completed"
            event_type = "orchestrator.job.completed"
            severity = "info"
        else:
            job.status = "failed"
            job.metadata["error"] = result.error
            event_type = "orchestrator.job.failed"
            severity = "error"
        self.queue.update(job)
        self._publish(
            event_type,
            job,
            payload={
                "success": result.success,
                "error": result.error,
                "failed_node": result.failed_node,
            },
            severity=severity,
        )
        return result

    def pause(self, job_id: str) -> OrchestratorJob:
        job = self.queue.pause(job_id)
        self._publish("orchestrator.job.paused", job)
        return job

    def resume(self, job_id: str) -> OrchestratorJob:
        job = self.queue.resume(job_id)
        self._publish("orchestrator.job.resumed", job)
        return job

    def cancel(self, job_id: str) -> OrchestratorJob:
        job = self.queue.cancel(job_id)
        self._publish("orchestrator.job.cancelled", job)
        return job

    def list_jobs(self, status: str | None = None) -> list[OrchestratorJob]:
        return self.queue.list(status=status)

    def status(self, job_id: str) -> dict[str, Any]:
        job = self._require_job(job_id)
        return to_plain(job)

    def stats(self) -> dict[str, Any]:
        jobs = self.queue.list()
        by_status = Counter(job.status for job in jobs)
        return {
            "path": str(self.queue.path),
            "total": len(jobs),
            "by_status": dict(sorted(by_status.items())),
            "running": by_status.get("running", 0),
            "queued": by_status.get("queued", 0) + by_status.get("ready", 0),
            "terminal": sum(by_status.get(status, 0) for status in TERMINAL_STATUSES),
        }

    def find_job_by_mission(self, mission_id: str) -> OrchestratorJob | None:
        jobs = [job for job in self.queue.list() if job.mission_id == mission_id]
        if not jobs:
            return None
        return sorted(jobs, key=lambda item: (item.created_at, item.id), reverse=True)[0]

    def pause_mission(self, mission_id: str) -> OrchestratorJob:
        return self.pause(self._require_job_for_mission(mission_id).id)

    def resume_mission(self, mission_id: str) -> OrchestratorJob:
        return self.resume(self._require_job_for_mission(mission_id).id)

    def cancel_mission(self, mission_id: str) -> OrchestratorJob:
        return self.cancel(self._require_job_for_mission(mission_id).id)

    def _mission_runtime(self):
        mission_runtime = getattr(self.core, "mission_runtime", None)
        if mission_runtime is None:
            raise RuntimeError("ExecutionOrchestratorRuntime requires MissionRuntime")
        return mission_runtime

    def _require_job(self, job_id: str) -> OrchestratorJob:
        job = self.queue.get(job_id)
        if job is None:
            raise KeyError(f"Orchestrator job not found: {job_id}")
        return job

    def _require_job_for_mission(self, mission_id: str) -> OrchestratorJob:
        job = self.find_job_by_mission(mission_id)
        if job is None:
            raise KeyError(f"Orchestrator job not found for mission: {mission_id}")
        return job

    def _skipped_result(self, job: OrchestratorJob, error: str) -> MissionResult:
        return MissionResult(
            success=False,
            completed_nodes=[],
            failed_node=None,
            report_path=None,
            error=error,
            metadata={"job_id": job.id, "job_status": job.status},
        )

    def _publish(
        self,
        event_type: str,
        job: OrchestratorJob,
        *,
        payload: dict[str, Any] | None = None,
        severity: str = "info",
    ) -> None:
        event_platform = getattr(self.core, "event_platform", None)
        publish = getattr(event_platform, "publish", None)
        if not callable(publish):
            return
        try:
            publish(
                event_type,
                "execution_orchestrator",
                {
                    "job_id": job.id,
                    "mission_id": job.mission_id,
                    "status": job.status,
                    **dict(payload or {}),
                },
                severity=severity,
                project_id=job.project_id,
                mission_id=job.mission_id,
                correlation_id=job.metadata.get("correlation_id"),
                metadata={"worker_id": job.worker_id},
            )
        except Exception:
            return
