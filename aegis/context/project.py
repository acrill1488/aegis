"""
Project Context for AEGIS AI Assistant
"""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class ProjectContext:
    """
    Represents the context of the AEGIS project including its name,
    description, components, and architecture summary.
    """

    project_name: str
    description: str
    components: List[str]
    current_architecture_summary: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ProjectContext to dictionary representation.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the project context
        """
        return {
            "project_name": self.project_name,
            "description": self.description,
            "components": self.components,
            "current_architecture_summary": self.current_architecture_summary
        }

    @classmethod
    def create_default(cls) -> "ProjectContext":
        """
        Create a default ProjectContext instance for AEGIS.
        
        Returns:
            ProjectContext: Default AEGIS project context
        """
        return cls(
            project_name="AEGIS",
            description="Локальный AI co-worker с расширенными возможностями для разработки и автоматизации задач",
            components=[
                "Runtime",
                "Agent Kernel",
                "Workspace",
                "Session",
                "Task",
                "Planner",
                "Executor",
                "Tool Registry",
                "Vision",
                "Image",
                "Memory",
                "n8n"
            ],
            current_architecture_summary="AEGIS представляет собой интегрированную систему AI-ассистента с модульной архитектурой, включающую runtime среду, ядро агента, рабочие пространства, сессии, планировщики задач, исполнители, реестры инструментов, визуальные компоненты и память."
        )


# Create default project context
DEFAULT_PROJECT_CONTEXT = ProjectContext.create_default()