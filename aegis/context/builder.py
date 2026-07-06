"""
Prompt Builder for AEGIS AI Assistant
"""

from typing import Optional, Dict, Any
from .project import PROJECT_CONTEXT
import json


class PromptBuilder:
    """
    Builder class for constructing prompts for the AEGIS AI assistant.
    """

    def __init__(self, project_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the PromptBuilder with an optional project context.
        
        Args:
            project_context (Optional[Dict[str, Any]]): The project context to use.
                If None, uses the default project context.
        """
        self.project_context = project_context or {
            "context": PROJECT_CONTEXT
        }
        self.memory_manager = None

    def set_memory_manager(self, memory_manager) -> None:
        """
        Set the memory manager for accessing memory records.
        
        Args:
            memory_manager: The MemoryManager instance to use
        """
        self.memory_manager = memory_manager

    def build_system_prompt(self) -> str:
        """
        Build the system prompt for AEGIS.
        
        Returns:
            str: The complete system prompt
        """
        # Load system prompt from file
        with open("prompts/system/aegis_ru.md", "r", encoding="utf-8") as f:
            system_prompt_template = f.read()
        
        # Replace placeholders with actual values
        memory_summary = "Память пуста"
        if self.memory_manager:
            try:
                records = self.memory_manager.list()
                if records:
                    memory_summary = f"Найдено {len(records)} записей в памяти:"
                    for record in records[:3]:  # Show first 3 records
                        memory_summary += f"\n- {record.title} ({record.type})"
            except Exception:
                # If we can't access memory, just use default message
                pass
        
        system_prompt = system_prompt_template.replace(
            "{{memory_summary}}",
            memory_summary
        )
        
        return system_prompt

    def build_prompt(self, workspace_context: Optional[Dict[str, Any]] = None, 
                   user_prompt: Optional[str] = None) -> str:
        """
        Build a complete prompt including system prompt, project context, workspace context and user prompt.
        
        Args:
            workspace_context (Optional[Dict[str, Any]]): Context about the current workspace
            user_prompt (Optional[str]): The user's specific question or request
            
        Returns:
            str: The complete constructed prompt
        """
        # Start with system prompt
        full_prompt = self.build_system_prompt()
        
        # Add workspace context if provided
        if workspace_context:
            full_prompt += f"\n\nКонтекст рабочей области:\n"
            for key, value in workspace_context.items():
                full_prompt += f"{key}: {value}\n"
        
        # Add user prompt if provided
        if user_prompt:
            full_prompt += f"\n\nВопрос пользователя:\n{user_prompt}"
        
        return full_prompt

    def get_project_context(self) -> Dict[str, Any]:
        """
        Get the current project context.
        
        Returns:
            Dict[str, Any]: The current project context
        """
        return self.project_context

    def set_project_context(self, project_context: Dict[str, Any]) -> None:
        """
        Set a new project context.
        
        Args:
            project_context (Dict[str, Any]): The new project context to use
        """
        self.project_context = project_context


# Create default prompt builder instance
DEFAULT_PROMPT_BUILDER = PromptBuilder()
