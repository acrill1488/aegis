from typing import Any, Dict

from aegis.prompt import PromptPackage, render_prompt_package

from ..context.builder import DEFAULT_PROMPT_BUILDER


class PromptBuilder:
    def __init__(self, core: "AegisCore"):
        self.core = core

    def build(
        self,
        user_prompt: str,
        context: Dict[str, Any],
        role: str = "assistant",
    ) -> str:
        """Build a formatted prompt with system, context and user request."""

        return render_prompt_package(self.compile(user_prompt, context, role))

    def compile(
        self,
        user_prompt: str,
        context: Dict[str, Any],
        role: str = "assistant",
    ) -> PromptPackage:
        """Build a compiled prompt package for runtime execution."""

        try:
            memory_summary = self.core.memory.list_summary()
        except Exception:
            memory_summary = "Память недоступна"

        knowledge_context = context.get("knowledge_context") if context else None
        return DEFAULT_PROMPT_BUILDER.compile_prompt(
            workspace_context=context,
            user_prompt=user_prompt,
            memory_summary=memory_summary,
            knowledge_context=knowledge_context,
        )
