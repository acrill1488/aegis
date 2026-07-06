"""Built-in AEGIS skills."""

from __future__ import annotations

from typing import Any

from aegis.skills.base import BaseSkill
from aegis.skills.models import SkillResult


RESEARCH_MARKERS = (
    "найди",
    "актуаль",
    "сейчас",
    "сегодня",
    "последн",
    "сравни",
    "исследуй",
    "ссылка",
    "url",
    "https://",
)

CODING_MARKERS = (
    "код",
    "python",
    "powershell",
    "git",
    "ошибка",
    "проект",
    "файл",
    "рефактор",
    "test",
    "pytest",
)

PLANNING_MARKERS = (
    "план",
    "задача",
    "разбей",
    "спланируй",
    "todo",
)

IDENTITY_MARKERS = (
    "кто ты",
    "что ты",
    "что такое aegis",
)

IDENTITY_RESPONSE = "Я — AEGIS, локальный ИИ-ассистент и co-worker пользователя."


class CoreSkill(BaseSkill):
    def __init__(self, core: Any):
        self.core = core

    def _run_agent(
        self,
        prompt: str,
        capability: str = "auto",
        role: str = "assistant",
    ) -> str:
        from aegis.agent.loop import AgentExecutionLoop

        agent_loop = getattr(self.core, "agent_loop", None)
        if agent_loop:
            return agent_loop.run(prompt, capability, role)
        return AgentExecutionLoop(self.core).run(prompt, capability, role)

    def _context_value(
        self,
        context: dict | None,
        key: str,
        default: str,
    ) -> str:
        if not context:
            return default
        return str(context.get(key) or default)


class ConversationSkill(CoreSkill):
    name = "conversation"
    description = "General conversation and default assistant responses."
    capabilities = ["general", "conversation"]

    def can_handle(self, prompt: str) -> bool:
        return True

    def execute(
        self,
        prompt: str,
        context: dict | None = None,
    ) -> SkillResult:
        normalized = prompt.lower().strip()
        if any(marker in normalized for marker in IDENTITY_MARKERS):
            return SkillResult(
                True,
                self.name,
                IDENTITY_RESPONSE,
                {"source": "builtin_identity"},
            )

        capability = self._context_value(context, "capability", "auto")
        role = self._context_value(context, "role", "assistant")
        output = self._run_agent(prompt, capability, role)
        return SkillResult(True, self.name, output, {"capability": capability})


class ResearchSkill(CoreSkill):
    name = "research"
    description = "Research with fresh context from Knowledge Engine."
    capabilities = ["research", "knowledge", "web"]

    def can_handle(self, prompt: str) -> bool:
        normalized = prompt.lower()
        return any(marker in normalized for marker in RESEARCH_MARKERS)

    def execute(
        self,
        prompt: str,
        context: dict | None = None,
    ) -> SkillResult:
        capability = self._context_value(context, "capability", "auto")
        role = self._context_value(context, "role", "assistant")
        context_bundle = self.core.context_builder.build(prompt)
        prompt_context = self.core.context_builder.to_prompt_context(context_bundle)
        enhanced_prompt = f"""{prompt_context}

USER REQUEST:
{prompt}

RULES:
Используй CONTEXT как приоритетный источник.
Если информации в CONTEXT недостаточно, честно скажи.
Если CONTEXT не содержит фактических данных по вопросу - не выдумывай.
Если пользователь просит актуальную/текущую информацию, Brain не имеет права отвечать только из внутренних знаний модели.
Ответь только финальным ответом на русском."""

        output = self._run_agent(enhanced_prompt, capability, role)
        return SkillResult(
            True,
            self.name,
            output,
            {
                "capability": capability,
                "sources": len(context_bundle.sources),
            },
        )


class CodingSkill(CoreSkill):
    name = "coding"
    description = "Coding, project, file, git, and test-oriented work."
    capabilities = ["coding"]

    def can_handle(self, prompt: str) -> bool:
        normalized = prompt.lower()
        return any(marker in normalized for marker in CODING_MARKERS)

    def execute(
        self,
        prompt: str,
        context: dict | None = None,
    ) -> SkillResult:
        role = self._context_value(context, "role", "assistant")
        output = self._run_agent(prompt, "coding", role)
        return SkillResult(True, self.name, output, {"capability": "coding"})


class PlanningSkill(CoreSkill):
    name = "planning"
    description = "Planning and task decomposition."
    capabilities = ["planning", "coding"]

    def can_handle(self, prompt: str) -> bool:
        normalized = prompt.lower()
        return any(marker in normalized for marker in PLANNING_MARKERS)

    def execute(
        self,
        prompt: str,
        context: dict | None = None,
    ) -> SkillResult:
        role = self._context_value(context, "role", "assistant")
        output = self._run_agent(prompt, "coding", role)
        return SkillResult(True, self.name, output, {"capability": "coding"})
