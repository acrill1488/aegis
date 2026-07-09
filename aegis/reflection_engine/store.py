from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import ReflectionRecommendation, ReflectionReport


class ReflectionStore:
    """Durable JSON storage for reflection reports and recommendations."""

    def __init__(
        self,
        reports_path: Path | str,
        recommendations_path: Path | str,
    ):
        self.reports_path = Path(reports_path)
        self.recommendations_path = Path(recommendations_path)
        self._ensure_file(self.reports_path)
        self._ensure_file(self.recommendations_path)

    def load_reports(self) -> list[ReflectionReport]:
        return [
            ReflectionReport.from_dict(item)
            for item in self._load_list(self.reports_path)
            if isinstance(item, dict)
        ]

    def load_recommendations(self) -> list[ReflectionRecommendation]:
        return [
            ReflectionRecommendation.from_dict(item)
            for item in self._load_list(self.recommendations_path)
            if isinstance(item, dict)
        ]

    def append_report(self, report: ReflectionReport) -> ReflectionReport:
        reports = self.load_reports()
        reports.append(report)
        self.save_reports(reports)
        return report

    def append_recommendations(
        self,
        recommendations: list[ReflectionRecommendation],
    ) -> list[ReflectionRecommendation]:
        if not recommendations:
            return []
        current = self.load_recommendations()
        current.extend(recommendations)
        self.save_recommendations(current)
        return recommendations

    def save_reports(self, reports: list[ReflectionReport]) -> None:
        self._save_list(self.reports_path, reports)

    def save_recommendations(
        self,
        recommendations: list[ReflectionRecommendation],
    ) -> None:
        self._save_list(self.recommendations_path, recommendations)

    def _ensure_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("[]", encoding="utf-8")

    def _load_list(self, path: Path) -> list[Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return data

    def _save_list(self, path: Path, values: list[Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(to_plain(values), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
