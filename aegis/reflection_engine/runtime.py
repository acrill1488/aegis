from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import ReflectionRecommendation, ReflectionReport
from .store import ReflectionStore


DEFAULT_REPORTS_PATH = Path(r"F:\AI_WORKSPACE\reflection\reports.json")
DEFAULT_RECOMMENDATIONS_PATH = Path(
    r"F:\AI_WORKSPACE\reflection\recommendations.json"
)


class ReflectionEngineRuntime:
    """Rule-based mission reflection that emits reports without changing behavior."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        store: ReflectionStore | None = None,
        reports_path: Path | str = DEFAULT_REPORTS_PATH,
        recommendations_path: Path | str = DEFAULT_RECOMMENDATIONS_PATH,
    ):
        self.core = core
        self.store = store or ReflectionStore(reports_path, recommendations_path)

    def analyze_mission(self, mission_id: str | None = None) -> ReflectionReport:
        mission = self._resolve_mission(mission_id)
        recovery_events = self._mission_recovery_events(mission)
        recovery_count = len(recovery_events)
        duration = self._duration_seconds(
            getattr(mission, "started_at", None),
            getattr(mission, "completed_at", None),
        )
        skill_failure_counts = self._skill_failure_counts()
        selector_patches = self._selector_patch_records()
        recommendations = self._recommendations(
            mission=mission,
            duration=duration,
            recovery_events=recovery_events,
            recovery_count=recovery_count,
            skill_failure_counts=skill_failure_counts,
            selector_patches=selector_patches,
        )
        warnings = self._warnings(
            mission=mission,
            duration=duration,
            recovery_count=recovery_count,
            recommendations=recommendations,
        )
        confidence = (
            max((recommendation.confidence for recommendation in recommendations), default=0.3)
            if recommendations
            else 0.3
        )
        report = ReflectionReport(
            mission_id=mission.id,
            project_id=mission.metadata.get("project_id"),
            goal=mission.goal,
            summary=self._summary(mission, recommendations),
            success=mission.status == "completed",
            duration=duration,
            recovery_count=recovery_count,
            warnings=warnings,
            recommendations=recommendations,
            confidence=confidence,
            metadata={
                "mission_status": mission.status,
                "skill_ids": [node.skill_id for node in mission.graph],
                "failed_nodes": [
                    node.id
                    for node in mission.graph
                    if node.status in {"failed", "blocked"}
                ],
                "recovery_events": recovery_events,
                "source": "reflection_engine_v1",
            },
        )
        self.store.append_report(report)
        self.store.append_recommendations(recommendations)
        self._record_experience(report)
        return report

    def list_reports(self, limit: int = 20) -> list[ReflectionReport]:
        reports = sorted(
            self.store.load_reports(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        return reports[: max(limit, 0)]

    def latest(self) -> ReflectionReport | None:
        reports = self.list_reports(limit=1)
        return reports[0] if reports else None

    def list_recommendations(
        self,
        status: str | None = None,
    ) -> list[ReflectionRecommendation]:
        recommendations = sorted(
            self.store.load_recommendations(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        if status is None:
            return recommendations
        return [
            recommendation
            for recommendation in recommendations
            if recommendation.status == status
        ]

    def stats(self) -> dict[str, Any]:
        reports = self.store.load_reports()
        recommendations = self.store.load_recommendations()
        by_type = Counter(recommendation.type for recommendation in recommendations)
        by_status = Counter(recommendation.status for recommendation in recommendations)
        successful_reports = sum(1 for report in reports if report.success)
        return {
            "reports_path": str(self.store.reports_path),
            "recommendations_path": str(self.store.recommendations_path),
            "report_count": len(reports),
            "recommendation_count": len(recommendations),
            "successful_report_count": successful_reports,
            "failed_report_count": len(reports) - successful_reports,
            "recommendations_by_type": dict(sorted(by_type.items())),
            "recommendations_by_status": dict(sorted(by_status.items())),
            "latest_report": to_plain(
                max(reports, key=lambda item: item.created_at, default=None)
            ),
        }

    def _resolve_mission(self, mission_id: str | None):
        mission_runtime = getattr(self.core, "mission_runtime", None)
        if mission_runtime is None:
            raise RuntimeError("Reflection Engine requires MissionRuntime")
        if mission_id is not None:
            return mission_runtime.show(mission_id)
        candidates = [
            mission
            for mission in mission_runtime.list()
            if mission.status in {"completed", "failed"}
        ]
        if not candidates:
            raise KeyError("No completed or failed missions found")
        return max(
            candidates,
            key=lambda mission: (
                mission.completed_at or mission.started_at or mission.created_at
            ),
        )

    def _recommendations(
        self,
        *,
        mission,
        duration: float | None,
        recovery_events: list[dict[str, Any]],
        recovery_count: int,
        skill_failure_counts: dict[str, int],
        selector_patches: list[Any],
    ) -> list[ReflectionRecommendation]:
        recommendations: list[ReflectionRecommendation] = []
        recovery_success = any(self._recovery_success(event) for event in recovery_events)

        if mission.status == "failed":
            recommendations.append(
                self._recommendation(
                    type="mission_failure",
                    target=mission.id,
                    priority="high",
                    reason="Mission finished with failed status.",
                    repeated=self._experience_count("mission.failure", mission.id) > 1,
                    recovery_success=recovery_success,
                    metadata={"mission_id": mission.id},
                )
            )
        if recovery_count > 0:
            recommendations.append(
                self._recommendation(
                    type="recovery_used",
                    target=mission.id,
                    priority="medium",
                    reason=f"Mission required {recovery_count} recovery attempt(s).",
                    repeated=recovery_count > 1,
                    recovery_success=recovery_success,
                    metadata={"mission_id": mission.id, "recovery_count": recovery_count},
                )
            )
        if recovery_count > 2:
            for skill_id in self._mission_skill_ids(mission):
                recommendations.append(
                    self._recommendation(
                        type="skill_unstable",
                        target=skill_id,
                        priority="high",
                        reason="Mission needed more than two recovery attempts.",
                        repeated=True,
                        recovery_success=recovery_success,
                        metadata={"mission_id": mission.id, "recovery_count": recovery_count},
                    )
                )
        if duration is not None and duration > 60:
            recommendations.append(
                self._recommendation(
                    type="performance",
                    target=mission.id,
                    priority="medium",
                    reason=f"Mission duration exceeded 60 seconds ({duration:.1f}s).",
                    repeated=False,
                    recovery_success=recovery_success,
                    metadata={"mission_id": mission.id, "duration": duration},
                )
            )
        if selector_patches:
            for patch in selector_patches:
                recommendations.append(
                    self._recommendation(
                        type="selector_update",
                        target=str(patch.source),
                        priority="medium",
                        reason="Recovered selector patch was recorded and may need review.",
                        repeated=self._experience_count(
                            "recovery.selector_patch",
                            str(patch.source),
                        ) > 1,
                        recovery_success=True,
                        metadata={
                            "mission_id": mission.id,
                            "selector_patch": to_plain(patch),
                        },
                    )
                )
        for skill_id in self._mission_skill_ids(mission):
            failure_count = skill_failure_counts.get(skill_id, 0)
            if failure_count > 1:
                recommendations.append(
                    self._recommendation(
                        type="skill_review",
                        target=skill_id,
                        priority="high",
                        reason=f"Skill failure was recorded {failure_count} times.",
                        repeated=True,
                        recovery_success=recovery_success,
                        metadata={
                            "mission_id": mission.id,
                            "skill_id": skill_id,
                            "failure_count": failure_count,
                        },
                    )
                )
        return recommendations

    def _recommendation(
        self,
        *,
        type: str,
        target: str,
        priority: str,
        reason: str,
        repeated: bool,
        recovery_success: bool,
        metadata: dict[str, Any],
    ) -> ReflectionRecommendation:
        confidence = 0.3
        if repeated:
            confidence += 0.2
        if recovery_success:
            confidence += 0.2
        return ReflectionRecommendation(
            type=type,
            target=target,
            priority=priority,
            reason=reason,
            confidence=min(confidence, 0.95),
            metadata=metadata,
        )

    def _warnings(
        self,
        *,
        mission,
        duration: float | None,
        recovery_count: int,
        recommendations: list[ReflectionRecommendation],
    ) -> list[str]:
        warnings: list[str] = []
        if mission.status == "failed":
            warnings.append("Mission failed.")
        if recovery_count > 0:
            warnings.append("Recovery was used during mission execution.")
        if recovery_count > 2:
            warnings.append("Recovery count indicates unstable execution.")
        if duration is not None and duration > 60:
            warnings.append("Mission execution took longer than 60 seconds.")
        if any(item.type == "skill_review" for item in recommendations):
            warnings.append("One or more skills have repeated failure history.")
        return warnings

    def _summary(
        self,
        mission,
        recommendations: list[ReflectionRecommendation],
    ) -> str:
        outcome = "succeeded" if mission.status == "completed" else mission.status
        if recommendations:
            return (
                f"Mission {mission.id} {outcome}; "
                f"{len(recommendations)} recommendation(s) generated."
            )
        return f"Mission {mission.id} {outcome}; no recommendations generated."

    def _mission_recovery_events(self, mission) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        node_ids = {node.id for node in mission.graph}
        for node in mission.graph:
            recovery = node.metadata.get("recovery")
            if not recovery:
                continue
            if isinstance(recovery, list):
                for item in recovery:
                    if isinstance(item, dict):
                        events.append(
                            {
                                "node_id": node.id,
                                "skill_id": node.skill_id,
                                "source": "mission_metadata",
                                **to_plain(item),
                            }
                        )
            elif isinstance(recovery, dict):
                events.append(
                    {
                        "node_id": node.id,
                        "skill_id": node.skill_id,
                        "source": "mission_metadata",
                        **to_plain(recovery),
                    }
                )
        for attempt in self._recovery_history():
            metadata = attempt.get("metadata") or {}
            node_id = metadata.get("node_id")
            source = str(attempt.get("source") or "")
            if node_id not in node_ids and not any(
                source == f"skill:{candidate}" for candidate in node_ids
            ):
                continue
            events.append(
                {
                    "node_id": str(node_id or source.removeprefix("skill:")),
                    "source": "recovery_history",
                    "strategy": attempt.get("strategy"),
                    "success": attempt.get("success"),
                    "error": attempt.get("error"),
                    "started_at": attempt.get("started_at"),
                    "completed_at": attempt.get("completed_at"),
                    "metadata": to_plain(metadata),
                }
            )
        return events

    def _recovery_history(self) -> list[dict[str, Any]]:
        recovery_engine = getattr(self.core, "recovery_engine", None)
        history = getattr(recovery_engine, "history", None)
        if not callable(history):
            return []
        try:
            return history()
        except Exception:
            return []

    def _selector_patch_records(self) -> list[Any]:
        operational_memory = getattr(self.core, "operational_memory", None)
        list_records = getattr(operational_memory, "list", None)
        if not callable(list_records):
            return []
        try:
            return list_records(type="recovery.selector_patch", limit=20)
        except Exception:
            return []

    def _skill_failure_counts(self) -> dict[str, int]:
        operational_memory = getattr(self.core, "operational_memory", None)
        list_records = getattr(operational_memory, "list", None)
        if not callable(list_records):
            return {}
        try:
            records = list_records(type="skill.failure", limit=1000)
        except Exception:
            return {}
        counts: dict[str, int] = defaultdict(int)
        for record in records:
            counts[str(record.source)] += 1
        return dict(counts)

    def _experience_count(self, type: str, source: str) -> int:
        operational_memory = getattr(self.core, "operational_memory", None)
        list_records = getattr(operational_memory, "list", None)
        if not callable(list_records):
            return 0
        try:
            return len(list_records(type=type, source=source, limit=1000))
        except Exception:
            return 0

    def _record_experience(self, report: ReflectionReport) -> None:
        operational_memory = getattr(self.core, "operational_memory", None)
        record = getattr(operational_memory, "record", None)
        if not callable(record):
            return
        try:
            record(
                {
                    "type": "reflection.report",
                    "source": "reflection_engine",
                    "summary": report.summary,
                    "confidence": report.confidence,
                    "data": {
                        "report_id": report.id,
                        "mission_id": report.mission_id,
                        "recommendations": to_plain(report.recommendations),
                    },
                    "metadata": {
                        "project_id": report.project_id,
                        "success": report.success,
                        "recovery_count": report.recovery_count,
                    },
                }
            )
        except Exception:
            return

    def _mission_skill_ids(self, mission) -> list[str]:
        return sorted({node.skill_id for node in mission.graph})

    def _recovery_success(self, event: dict[str, Any]) -> bool:
        if event.get("retry_success") is True:
            return True
        if event.get("success") is True:
            return True
        nested = event.get("recovery")
        if isinstance(nested, dict):
            return self._recovery_success(nested)
        if isinstance(nested, list):
            return any(
                self._recovery_success(item)
                for item in nested
                if isinstance(item, dict)
            )
        return False

    def _duration_seconds(
        self,
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> float | None:
        if started_at is None or completed_at is None:
            return None
        return (completed_at - started_at).total_seconds()
