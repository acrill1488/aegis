from __future__ import annotations

import re

from .models import PlannerContext, PlannerStep


RULES = [
    ("википеди", "browser.wikipedia.search", "Search Wikipedia"),
    ("wikipedia", "browser.wikipedia.search", "Search Wikipedia"),
    ("github", "browser.github.search", "Search GitHub"),
    ("презентаци", "presentation.create", "Create presentation"),
    ("presentation", "presentation.create", "Create presentation"),
    ("pdf", "pdf.extract", "Extract PDF content"),
]


def build_steps(context: PlannerContext) -> list[PlannerStep]:
    goal = context.goal.casefold()
    steps: list[PlannerStep] = []
    seen: set[str] = set()

    for keyword, skill_id, title in RULES:
        if keyword not in goal or skill_id in seen:
            continue
        seen.add(skill_id)
        steps.append(
            PlannerStep(
                id=f"step_{len(steps) + 1}",
                title=title,
                skill_id=skill_id,
                priority=50,
                dependencies=[],
                estimated_duration=_duration_for(skill_id),
                confidence=_base_confidence(skill_id),
                metadata={
                    "heuristic": "keyword",
                    "keyword": keyword,
                    "inputs": {"query": extract_query(context.goal, keyword)},
                },
            )
        )

    if not steps:
        steps.append(
            PlannerStep(
                id="step_1",
                title="Review goal manually",
                skill_id="planner.unresolved",
                priority=10,
                dependencies=[],
                estimated_duration=60.0,
                confidence=0.1,
                metadata={
                    "heuristic": "fallback",
                    "warning": "No heuristic rule matched this goal.",
                    "inputs": {"goal": context.goal},
                },
            )
        )
    return steps


def extract_query(goal: str, keyword: str) -> str:
    query = goal
    query = re.sub(r"\b(wikipedia|wiki)\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\bвикипеди\w*\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\bgithub\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\bпрезентаци\w*\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(rf"\b{re.escape(keyword)}\w*\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(
        r"^\s*(find|search|lookup|look up|найди|найти|поищи|искать|создай|сделай)\s+",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\b(in|on|at|about|for|в|на|о|об|про)\b\s*$", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" \t\r\n:-.,;\"'")
    return query or goal.strip()


def _base_confidence(skill_id: str) -> float:
    if skill_id.startswith("browser."):
        return 0.75
    if skill_id in {"presentation.create", "pdf.extract"}:
        return 0.7
    return 0.5


def _duration_for(skill_id: str) -> float:
    durations = {
        "browser.wikipedia.search": 20.0,
        "browser.github.search": 25.0,
        "presentation.create": 180.0,
        "pdf.extract": 45.0,
    }
    return durations.get(skill_id, 60.0)
