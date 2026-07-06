"""Default prompt blocks for AEGIS."""

from __future__ import annotations

from typing import Any

from aegis.protocol import build_response_protocol_instruction

from .contracts import PromptBlock


DEFAULT_PROJECT_CONTEXT = """\
AEGIS - локальная AI Operating System и локальный AI co-worker пользователя.
Если пользователь говорит "AEGIS", речь идет об этом проекте.
Не раскрывай название модели.
"""


OUTPUT_RULES = """\
- Отвечай на русском языке.
- Не выводи reasoning или ход внутреннего анализа.
- Не выводи теги <think>.
- Не выводи JSON tool calls.
- Если есть свежий knowledge context, используй его как приоритетный источник.
"""


def create_default_blocks(context: dict[str, Any] | None = None) -> list[PromptBlock]:
    """Create the standard Prompt Compiler v1 block set."""

    data = context or {}
    return [
        PromptBlock(
            name="identity",
            content="Ты - AEGIS, локальный AI co-worker пользователя.",
            priority=10,
        ),
        PromptBlock(
            name="project_context",
            content=str(data.get("project_context") or DEFAULT_PROJECT_CONTEXT).strip(),
            priority=20,
        ),
        PromptBlock(
            name="output_rules",
            content=OUTPUT_RULES.strip(),
            priority=30,
        ),
        PromptBlock(
            name="response_protocol",
            content=build_response_protocol_instruction(),
            priority=35,
        ),
        PromptBlock(
            name="knowledge_context",
            content=str(data.get("knowledge_context") or "").strip(),
            priority=40,
            enabled=bool(data.get("knowledge_context")),
        ),
        PromptBlock(
            name="memory_summary",
            content=str(data.get("memory_summary") or "").strip(),
            priority=50,
            enabled=bool(data.get("memory_summary")),
        ),
        PromptBlock(
            name="workspace_context",
            content=str(data.get("workspace_context") or "").strip(),
            priority=60,
            enabled=bool(data.get("workspace_context")),
        ),
    ]
