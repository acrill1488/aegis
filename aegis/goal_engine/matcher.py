from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from aegis.skill_engine import SkillRegistry

from .models import Goal


class RuleBasedSkillMatcher:
    """Maps natural-language goals to known Skill Engine skills."""

    _WIKIPEDIA_RE = re.compile(r"\b(wikipedia)\b|википед", re.IGNORECASE)
    _GITHUB_RE = re.compile(r"\bgithub\b", re.IGNORECASE)
    _HUGGINGFACE_RE = re.compile(r"\bhuggingface\b", re.IGNORECASE)

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def match(self, text: str) -> Goal:
        normalized = text.strip()
        if self._WIKIPEDIA_RE.search(normalized):
            return self._goal(
                text=normalized,
                intent="search.wikipedia",
                confidence=0.9,
                skill_id="browser.wikipedia.search",
                inputs={"query": self._extract_wikipedia_query(normalized)},
            )
        if self._GITHUB_RE.search(normalized):
            return self._goal(
                text=normalized,
                intent="search.github_repository",
                confidence=0.8,
                skill_id="github.search_repository",
                inputs={"query": self._extract_keyword_query(normalized, "github")},
            )
        if self._HUGGINGFACE_RE.search(normalized):
            return self._goal(
                text=normalized,
                intent="search.huggingface_model",
                confidence=0.8,
                skill_id="huggingface.search_model",
                inputs={
                    "query": self._extract_keyword_query(normalized, "huggingface"),
                },
            )
        return Goal(
            id=self._new_id(),
            text=normalized,
            intent="unresolved",
            confidence=0.0,
            selected_skill=None,
            inputs={},
            metadata={"status": "unresolved", "reason": "no_matching_rule"},
        )

    def _goal(
        self,
        *,
        text: str,
        intent: str,
        confidence: float,
        skill_id: str,
        inputs: dict[str, Any],
    ) -> Goal:
        available = self.registry.get(skill_id) is not None
        return Goal(
            id=self._new_id(),
            text=text,
            intent=intent,
            confidence=confidence,
            selected_skill=skill_id,
            inputs=inputs,
            metadata={
                "status": "matched" if available else "not_available",
                "skill_available": available,
            },
        )

    def _extract_wikipedia_query(self, text: str) -> str:
        query = re.sub(r"\bWikipedia\b", " ", text, flags=re.IGNORECASE)
        query = re.sub(r"\b(wiki)\b", " ", query, flags=re.IGNORECASE)
        query = re.sub(r"\bвикипед\w*\b", " ", query, flags=re.IGNORECASE)
        query = self._strip_search_words(query)
        query = re.sub(r"\b(in|on|at|about|for|в|на|о|об|про)\b\s*$", "", query, flags=re.IGNORECASE)
        return self._clean_query(query) or text.strip()

    def _extract_keyword_query(self, text: str, keyword: str) -> str:
        query = re.sub(rf"\b{re.escape(keyword)}\b", " ", text, flags=re.IGNORECASE)
        query = self._strip_search_words(query)
        return self._clean_query(query) or text.strip()

    def _strip_search_words(self, text: str) -> str:
        return re.sub(
            r"^\s*(find|search|lookup|look up|найди|найти|поищи|искать)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )

    def _clean_query(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip(" \t\r\n:-.,;\"'")

    def _new_id(self) -> str:
        return f"goal_{uuid4().hex}"
