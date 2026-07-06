"""Skill registry and prompt detection."""

from __future__ import annotations

from aegis.skills.base import BaseSkill


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def detect(self, prompt: str) -> BaseSkill | None:
        for skill in self._skills.values():
            if getattr(skill, "enabled", True) and skill.can_handle(prompt):
                return skill
        return None
