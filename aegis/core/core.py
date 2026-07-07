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
from aegis.system import SystemAPI

class AegisCore:
    def __init__(self):
        self.runtime = RuntimeManager()
        self.workspace = WorkspaceManager()
        self.tasks = TaskManager()
        self.tools = ToolRegistry()
        self.registry = ServiceRegistry()
        self.router = CapabilityRouter()
        self.memory = MemoryManager()
        self.system = SystemAPI()
        
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

        # Initialize agent loop
        from aegis.agent.loop import AgentExecutionLoop
        self.agent_loop = AgentExecutionLoop(self)
        self.registry.register("agent_loop", self.agent_loop)
        
        # Register memory
        self.registry.register("memory", self.memory)

        # Register system status API
        self.registry.register("system", self.system)
        
        # Initialize web browser
        from aegis.web.browser import WebBrowser
        self.web = WebBrowser(self)
        self.registry.register("web", self.web)

        # Initialize knowledge engine
        from aegis.knowledge.engine import KnowledgeEngine
        self.knowledge = KnowledgeEngine(self)
        self.registry.register("knowledge", self.knowledge)

        # Initialize context builder
        from aegis.context.builder_v2 import ContextBuilderV2
        self.context_builder = ContextBuilderV2(self)
        self.registry.register("context_builder", self.context_builder)

        # Initialize skills
        from aegis.skills.builtin import (
            CodingSkill,
            ConversationSkill,
            PlanningSkill,
            ResearchSkill,
        )
        from aegis.skills.registry import SkillRegistry

        self.skills = SkillRegistry()
        self.skills.register(ResearchSkill(self))
        self.skills.register(CodingSkill(self))
        self.skills.register(PlanningSkill(self))
        self.skills.register(ConversationSkill(self))
        self.registry.register("skills", self.skills)

        # Initialize brain engine
        from aegis.brain.engine import BrainEngine
        self.brain = BrainEngine(self)
        self.registry.register("brain", self.brain)
        
        # Initialize reflection engine
        from aegis.brain.reflection import ReflectionEngine
        self.reflection = ReflectionEngine(self)
        self.registry.register("reflection", self.reflection)

    def get_task(self, task_id: str):
        return self.tasks.get(task_id)

    def list_tasks(self):
        return self.tasks.list()

    def save_task(self, task):
        return self.tasks.save(task)
