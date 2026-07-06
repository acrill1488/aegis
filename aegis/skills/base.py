"""Base contract for executable AEGIS skills."""

from __future__ import annotations

from aegis.skills.models import SkillResult


class BaseSkill:
    name: str
    description: str
    capabilities: list[str]
    enabled: bool = True

    def can_handle(self, prompt: str) -> bool:
        raise NotImplementedError

    def execute(
        self,
        prompt: str,
        context: dict | None = None,
    ) -> SkillResult:
        raise NotImplementedError
