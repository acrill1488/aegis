import os
import platform
from pathlib import Path
from aegis.runtime.manager import RuntimeManager
from aegis.runtime.scheduler import Scheduler
from aegis.workspace.manager import WorkspaceManager
from aegis.task.manager import TaskManager
from aegis.tools.registry import ToolRegistry
from aegis.planner.planner import Planner
from aegis.core.registry import ServiceRegistry
from aegis.executor.executor import ExecutionEngine
from aegis.router.capability import CapabilityRouter
from aegis.events import EventBus
from aegis.memory.manager import MemoryManager
from aegis.models import ModelRegistry, ModelRuntime
from aegis.models.providers import OllamaProvider
from aegis.system import SystemAPI
from aegis.live import ContextStore
from aegis.agents.runtime import AgentRuntime, EchoAgent
from aegis.capabilities import CapabilityDescriptor, CapabilityRuntime
from aegis.distributed import MachineRegistry
from aegis.mcp_runtime import MCPRuntime
from aegis.planning import TaskPlanningRuntime
from aegis.services import ServiceRuntime
from aegis.ui_intelligence import UIIntelligenceRuntime
from aegis.executor import ExecutorRuntime
from aegis.scenarios import ScenarioRuntime
from aegis.skill_engine import SkillEngineRuntime
from aegis.goal_engine import GoalEngineRuntime
from aegis.mission_engine import MissionRuntime
from aegis.project_runtime import ProjectRuntime
from aegis.recovery_engine import RecoveryEngineRuntime
from aegis.operational_memory import OperationalMemoryRuntime
from aegis.reflection_engine import ReflectionEngineRuntime

class AegisCore:
    def __init__(self):
        self.runtime = RuntimeManager()
        self.scheduler = Scheduler()
        self.workspace = WorkspaceManager()
        self.tasks = TaskManager()
        self.tools = ToolRegistry()
        self.registry = ServiceRegistry()
        self.router = CapabilityRouter()
        self.events = EventBus()
        self.registry.register("scheduler", self.scheduler)
        self.registry.register("watcher_registry", self.scheduler.watcher_registry)
        self.registry.register("events", self.events)
        self.machine_registry = MachineRegistry()
        self.machine_registry.event_bus = self.events
        self.registry.register("machine_registry", self.machine_registry)
        self.model_registry = ModelRegistry()
        self.model_registry.seed_defaults()
        self.registry.register("model_registry", self.model_registry)
        self.model_runtime = ModelRuntime(
            model_registry=self.model_registry,
            providers={"ollama": OllamaProvider()},
        )
        self.registry.register("model_runtime", self.model_runtime)
        self.agent_runtime = AgentRuntime(self)
        self.registry.register("agent_runtime", self.agent_runtime)
        self.service_runtime = ServiceRuntime(self)
        self.registry.register("service_runtime", self.service_runtime)
        self.capability_runtime = CapabilityRuntime(self)
        self.registry.register("capability_runtime", self.capability_runtime)
        self.executor_runtime = ExecutorRuntime(
            capability_runtime=self.capability_runtime,
            core=self,
        )
        self.registry.register("executor_runtime", self.executor_runtime)
        self.ui_intelligence = UIIntelligenceRuntime(self)
        self.registry.register("ui_intelligence", self.ui_intelligence)
        self.mcp_runtime = MCPRuntime(self)
        self.registry.register("mcp_runtime", self.mcp_runtime)
        self.task_planning_runtime = TaskPlanningRuntime(
            capability_runtime=self.capability_runtime,
        )
        self.registry.register("task_planning_runtime", self.task_planning_runtime)
        self.scenario_runtime = ScenarioRuntime(self)
        self.registry.register("scenario_runtime", self.scenario_runtime)
        self.operational_memory = OperationalMemoryRuntime(self)
        self.registry.register("operational_memory", self.operational_memory)
        self.recovery_engine = RecoveryEngineRuntime(self)
        self.registry.register("recovery_engine", self.recovery_engine)
        self.skill_engine = SkillEngineRuntime(self)
        self.registry.register("skill_engine", self.skill_engine)
        self.project_runtime = ProjectRuntime(self)
        self.registry.register("project_runtime", self.project_runtime)
        self.mission_runtime = MissionRuntime(self, skill_engine=self.skill_engine)
        self.registry.register("mission_runtime", self.mission_runtime)
        self.reflection_engine = ReflectionEngineRuntime(self)
        self.registry.register("reflection_engine", self.reflection_engine)
        self.goal_engine = GoalEngineRuntime(
            self,
            skill_engine=self.skill_engine,
            mission_runtime=self.mission_runtime,
        )
        self.registry.register("goal_engine", self.goal_engine)
        self.agent_runtime.register(EchoAgent())
        if platform.system().lower() == "windows":
            from aegis.agents.windows import WindowsAgent

            self.agent_runtime.register(WindowsAgent(self))
        from aegis.agents.browser import BrowserAgent

        self.agent_runtime.register(BrowserAgent(self))
        self.capability_runtime.register_agent_capabilities()
        self.capability_runtime.register(
            CapabilityDescriptor(
                id="executor.execute",
                name="Execute Agent Executor Plan",
                version="1",
                owner_agent="executor_runtime",
                machine_scope="local",
                permissions=["executor.execute"],
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                tags=["executor", "runtime", "planning"],
                metadata={
                    "description": "Run Observe/Reason/Action/Validate execution plans.",
                    "side_effects": ["capability.invoke"],
                },
            ),
            {
                "type": "runtime",
                "runtime": "executor_runtime",
                "method": "execute_payload",
            },
        )
        self.ui_intelligence.register_capabilities()
        self.mcp_runtime.auto_discover_enabled()
        self.memory = MemoryManager(event_bus=self.events)
        self.live_context = ContextStore()
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

        # Register current live context
        self.registry.register("live_context", self.live_context)

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
