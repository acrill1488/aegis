import os
from pathlib import Path
from aegis.runtime.manager import RuntimeManager
from aegis.workspace.manager import WorkspaceManager
from aegis.task.manager import TaskManager
from aegis.tools.registry import ToolRegistry
from aegis.planner.planner import Planner
from aegis.core.registry import ServiceRegistry

class AegisCore:
    def __init__(self):
        self.runtime = RuntimeManager()
        self.workspace = WorkspaceManager()
        self.tasks = TaskManager()
        self.tools = ToolRegistry()
        self.registry = ServiceRegistry()
        
        # Initialize planner
        self.planner = Planner(self)
        self.registry.register("planner", self.planner)

    def get_task(self, task_id: str):
        return self.tasks.get(task_id)

    def list_tasks(self):
        return self.tasks.list()

    def save_task(self, task):
        return self.tasks.save(task)