"""Prompt builder facade for AEGIS AI Assistant."""

from typing import Any, Optional

from aegis.prompt import PromptCompiler, PromptPackage, render_prompt_package

from .project import PROJECT_CONTEXT


class PromptBuilder:
    """Backward-compatible builder backed by Prompt Compiler v1."""

    def __init__(self, project_context: Optional[dict[str, Any]] = None):
        self.project_context = project_context or {
            "context": PROJECT_CONTEXT,
        }
        self.memory_manager = None
        self.compiler = PromptCompiler()

    def set_memory_manager(self, memory_manager) -> None:
        """Set the memory manager for accessing memory records."""

        self.memory_manager = memory_manager

    def build_system_prompt(self) -> str:
        """Build only the system prompt section."""

        package = self.compile_prompt()
        return package.system

    def compile_prompt(
        self,
        workspace_context: Optional[dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
        memory_summary: Optional[str] = None,
        knowledge_context: Optional[str] = None,
    ) -> PromptPackage:
        """Compile a prompt package using Prompt Compiler v1."""

        context = {
            "project_context": self.project_context.get("context", PROJECT_CONTEXT),
            "workspace_context": workspace_context or {},
            "memory_summary": memory_summary or self._build_memory_summary(),
            "knowledge_context": knowledge_context,
        }
        return self.compiler.compile(user_prompt or "", context)

    def build_prompt(
        self,
        workspace_context: Optional[dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
        memory_summary: Optional[str] = None,
        knowledge_context: Optional[str] = None,
    ) -> str:
        """Build a complete prompt string for existing runtime adapters."""

        package = self.compile_prompt(
            workspace_context=workspace_context,
            user_prompt=user_prompt,
            memory_summary=memory_summary,
            knowledge_context=knowledge_context,
        )
        return render_prompt_package(package)

    def get_project_context(self) -> dict[str, Any]:
        """Get the current project context."""

        return self.project_context

    def set_project_context(self, project_context: dict[str, Any]) -> None:
        """Set a new project context."""

        self.project_context = project_context

    def _build_memory_summary(self) -> str:
        memory_summary = "Память пуста"
        if self.memory_manager:
            try:
                records = self.memory_manager.list()
                if records:
                    memory_summary = f"Найдено {len(records)} записей в памяти:"
                    for record in records[:3]:
                        memory_summary += f"\n- {record.title} ({record.type})"
            except Exception:
                pass
        return memory_summary


DEFAULT_PROMPT_BUILDER = PromptBuilder()
