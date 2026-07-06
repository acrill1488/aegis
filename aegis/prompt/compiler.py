"""Prompt Compiler v1."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .blocks import create_default_blocks
from .contracts import PromptBlock, PromptPackage


class PromptCompiler:
    """Compile user input and structured context into a prompt package."""

    def __init__(self, blocks: list[PromptBlock] | None = None):
        self._blocks: list[PromptBlock] = list(blocks or [])

    def add_block(self, block: PromptBlock) -> None:
        """Add or replace a prompt block by name."""

        self._blocks = [existing for existing in self._blocks if existing.name != block.name]
        self._blocks.append(block)

    def compile(
        self,
        user_prompt: str,
        context: dict[str, Any] | None = None,
    ) -> PromptPackage:
        """Return a compiled prompt package."""

        data = context or {}
        blocks_by_name = {
            block.name: block
            for block in create_default_blocks(data)
        }
        for block in self._blocks:
            blocks_by_name[block.name] = block
        blocks = list(blocks_by_name.values())

        enabled_blocks = sorted(
            (block for block in blocks if block.enabled and block.content.strip()),
            key=lambda block: (block.priority, block.name),
        )

        system_names = {"identity", "project_context", "output_rules"}
        system_blocks = [block for block in enabled_blocks if block.name in system_names]
        context_blocks = [block for block in enabled_blocks if block.name not in system_names]

        return PromptPackage(
            system=self._render_blocks(system_blocks),
            context=self._render_blocks(context_blocks),
            user=user_prompt,
            metadata={
                "compiler": "prompt-compiler-v1",
                "blocks": [asdict(block) for block in enabled_blocks],
                "fresh_knowledge": bool(data.get("knowledge_context")),
            },
        )

    @staticmethod
    def _render_blocks(blocks: list[PromptBlock]) -> str:
        rendered: list[str] = []
        for block in blocks:
            rendered.append(f"[{block.name}]\n{block.content.strip()}")
        return "\n\n".join(rendered)


def render_prompt_package(package: PromptPackage) -> str:
    """Render a prompt package as a backward-compatible runtime string."""

    parts = [
        ("SYSTEM", package.system),
        ("CONTEXT", package.context),
        ("USER", package.user),
    ]
    prompt = "\n\n".join(
        f"{title}:\n{content.strip()}"
        for title, content in parts
        if content and content.strip()
    )
    return prompt
