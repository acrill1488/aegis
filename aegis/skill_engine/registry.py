from __future__ import annotations

from pathlib import Path

from .loader import SkillLoader
from .models import Skill


DEFAULT_SKILL_ROOT = Path("F:/AI_WORKSPACE/skills")


class SkillRegistry:
    """In-memory registry for YAML skill graph definitions."""

    def __init__(
        self,
        *,
        loader: SkillLoader | None = None,
        default_root: str | Path = DEFAULT_SKILL_ROOT,
    ):
        self.loader = loader or SkillLoader()
        self.default_root = Path(default_root)
        self._skills: dict[str, Skill] = {}

    def load_defaults(self) -> list[Skill]:
        skills = self.loader.load_dir(self.default_root)
        for skill in skills:
            self.register(skill)
        return skills

    def register(self, skill: Skill) -> Skill:
        if not skill.id:
            raise ValueError("Skill id is required")
        self._skills[skill.id] = skill
        return skill

    def get(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def list(self) -> list[Skill]:
        return [self._skills[key] for key in sorted(self._skills)]

    def find_by_tag(self, tag: str) -> list[Skill]:
        wanted = tag.casefold()
        matches: list[Skill] = []
        for skill in self.list():
            tags = skill.metadata.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            if any(str(item).casefold() == wanted for item in tags):
                matches.append(skill)
        return matches
