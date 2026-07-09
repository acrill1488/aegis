from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aegis.ipc import IPCClient
from aegis.serialization import to_json, to_plain

from .models import ScenarioRunResult, ScenarioStep
from .registry import ScenarioRegistry


DEFAULT_REPORT_DIR = Path("F:/AI_WORKSPACE/scenarios/runs")


class ScenarioRuntime:
    """Executes scenario steps through the daemon IPC boundary."""

    _ACTION_ROUTES = {
        "browser.open": ("browser", "open"),
        "browser.fill": ("browser", "fill"),
        "browser.press": ("browser", "press"),
        "browser.wait": ("browser", "wait"),
        "browser.text": ("browser", "text"),
        "browser.screenshot": ("browser", "screenshot"),
        "ui.observe": ("ui", "observe"),
        "ui.locate": ("ui", "locate"),
    }

    def __init__(
        self,
        core: Any | None = None,
        *,
        registry: ScenarioRegistry | None = None,
        ipc_client: IPCClient | None = None,
        report_dir: Path | str = DEFAULT_REPORT_DIR,
    ):
        self.core = core
        self.scenarios = registry or ScenarioRegistry()
        self.scenarios.seed_defaults()
        self.ipc_client = ipc_client or IPCClient()
        self.report_dir = Path(report_dir)

    def run(self, scenario_id: str) -> ScenarioRunResult:
        scenario = self.scenarios.get(scenario_id)
        if scenario is None:
            raise KeyError(f"Scenario not found: {scenario_id}")

        started_at = self._now()
        step_results: list[dict[str, Any]] = []
        error: str | None = None
        success = True

        for step in scenario.steps:
            try:
                result = self.run_step(step)
            except Exception as exc:
                result = {
                    "step_id": step.id,
                    "action": step.action,
                    "success": False,
                    "output": None,
                    "expect": to_plain(step.expect),
                    "validation": {
                        "success": False,
                        "errors": [str(exc)],
                    },
                    "error": str(exc),
                    "metadata": to_plain(step.metadata),
                }
            step_results.append(result)
            if not result.get("success"):
                success = False
                error = result.get("error") or "; ".join(
                    result.get("validation", {}).get("errors", [])
                )
                break

        completed_at = self._now()
        run_result = ScenarioRunResult(
            scenario_id=scenario.id,
            success=success,
            started_at=started_at,
            completed_at=completed_at,
            step_results=step_results,
            error=error,
            metadata={
                "scenario_name": scenario.name,
                "report_path": str(
                    self._report_path(scenario.id, started_at)
                ),
            },
        )
        report_path = self._save_report(run_result)
        run_result.metadata["report_path"] = str(report_path)
        return run_result

    def run_step(self, step: ScenarioStep) -> dict[str, Any]:
        target, action = self._route(step.action)
        started_at = self._now()
        output = self.ipc_client.request(target, action, step.payload)
        completed_at = self._now()
        validation = self.validate_expect(output, step.expect)
        return {
            "step_id": step.id,
            "action": step.action,
            "success": validation["success"],
            "started_at": started_at,
            "completed_at": completed_at,
            "payload": to_plain(step.payload),
            "output": to_plain(output),
            "expect": to_plain(step.expect),
            "validation": validation,
            "metadata": to_plain(step.metadata),
        }

    def validate_expect(self, output: Any, expect: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        if not expect:
            return {"success": True, "errors": errors}

        if "contains_text" in expect:
            wanted = str(expect["contains_text"])
            if wanted.casefold() not in self._flatten_text(output).casefold():
                errors.append(f"Expected output to contain text: {wanted}")

        if "url_contains" in expect:
            wanted = str(expect["url_contains"])
            url = self._find_key(output, "url")
            if wanted.casefold() not in str(url or "").casefold():
                errors.append(f"Expected url to contain: {wanted}")

        if "title_contains" in expect:
            wanted = str(expect["title_contains"])
            title = self._find_key(output, "title")
            if wanted.casefold() not in str(title or "").casefold():
                errors.append(f"Expected title to contain: {wanted}")

        if "element_exists" in expect and bool(expect["element_exists"]):
            if not self._element_exists(output):
                errors.append("Expected an element to exist")

        if "success_true" in expect and bool(expect["success_true"]):
            success_value = self._find_key(output, "success")
            if success_value is not True:
                errors.append("Expected output.success to be true")

        return {"success": not errors, "errors": errors}

    def _route(self, action: str) -> tuple[str, str]:
        route = self._ACTION_ROUTES.get(action)
        if route is None:
            raise ValueError(f"Unsupported scenario action: {action}")
        return route

    def _save_report(self, result: ScenarioRunResult) -> Path:
        path = self._report_path(result.scenario_id, result.started_at)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(to_json(result), encoding="utf-8")
        return path

    def _report_path(self, scenario_id: str, started_at: datetime) -> Path:
        timestamp = started_at.strftime("%Y%m%d-%H%M%S")
        safe_id = scenario_id.replace("/", "_").replace("\\", "_")
        return self.report_dir / f"{timestamp}-{safe_id}.json"

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _flatten_text(self, value: Any) -> str:
        plain = to_plain(value)
        if plain is None:
            return ""
        if isinstance(plain, (str, int, float, bool)):
            return str(plain)
        if isinstance(plain, dict):
            return " ".join(self._flatten_text(item) for item in plain.values())
        if isinstance(plain, list):
            return " ".join(self._flatten_text(item) for item in plain)
        return str(plain)

    def _find_key(self, value: Any, wanted_key: str) -> Any:
        plain = to_plain(value)
        if isinstance(plain, dict):
            if wanted_key in plain:
                return plain[wanted_key]
            for item in plain.values():
                found = self._find_key(item, wanted_key)
                if found is not None:
                    return found
        if isinstance(plain, list):
            for item in plain:
                found = self._find_key(item, wanted_key)
                if found is not None:
                    return found
        return None

    def _element_exists(self, output: Any) -> bool:
        plain = to_plain(output)
        if not plain:
            return False
        if isinstance(plain, dict):
            best_match = plain.get("best_match")
            if best_match:
                return True
            matches = plain.get("matches")
            if isinstance(matches, list) and len(matches) > 0:
                return True
            elements = plain.get("elements")
            if isinstance(elements, list) and len(elements) > 0:
                return True
        return False
