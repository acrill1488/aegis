import os
from pathlib import Path
from aegis.runtime.manager import RuntimeManager
from aegis.workspace.manager import WorkspaceManager
from aegis.task.manager import TaskManager
from aegis.tools.registry import ToolRegistry
from aegis.planner.planner import Planner
from aegis.core.registry import ServiceRegistry
from aegis.executor.executor import ExecutionEngine
from aegis.router.capability import CapabilityRouter
from aegis.memory.manager import MemoryManager

class AegisCore:
    def __init__(self):
        self.runtime = RuntimeManager()
        self.workspace = WorkspaceManager()
        self.tasks = TaskManager()
        self.tools = ToolRegistry()
        self.registry = ServiceRegistry()
        self.router = CapabilityRouter()
        self.memory = MemoryManager()
        
        # Register tools
        from aegis.tools.filesystem import FilesystemTool
        from aegis.tools.powershell import PowerShellTool
        from aegis.tools.git import GitTool
        
        self.tools.register(FilesystemTool())
        self.tools.register(PowerShellTool())
        self.tools.register(GitTool())
        
        # Initialize planner
        self.planner = Planner(self)
        self.registry.register("planner", self.planner)
        
        # Initialize executor
        self.executor = ExecutionEngine(self)
        self.registry.register("executor", self.executor)
        
        # Initialize agent kernel
        from aegis.agent.kernel import AgentKernel
        self.agent = AgentKernel(self)
        self.registry.register("agent", self.agent)
        
        # Register memory
        self.registry.register("memory", self.memory)
        
        # Initialize brain engine
        from aegis.brain.engine import BrainEngine
        self.brain = BrainEngine(self)
        self.registry.register("brain", self.brain)
        
        # Initialize reflection engine
        from aegis.brain.reflection import ReflectionEngine
        self.reflection = ReflectionEngine(self)
        self.registry.register("reflection", self.reflection)
        
        # Initialize web browser
        from aegis.web.browser import WebBrowser
        self.web = WebBrowser(self)
        self.registry.register("web", self.web)

    def get_task(self, task_id: str):
        return self.tasks.get(task_id)

    def list_tasks(self):
        return self.tasks.list()

    def save_task(self, task):
        return self.tasks.save(task)
