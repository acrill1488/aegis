from aegis.planner.models import ExecutionPlan, PlanStep
from aegis.planner.prompts import build_planning_prompt
from aegis.planner.parser import parse_plan_response
from aegis.task.manager import TaskManager
from aegis.task.models import TaskStep
from aegis.task.status import TaskStatus

class Planner:
    def __init__(self, core):
        self.core = core
    
    def create_plan(self, task_id: str, capability: str = "coding") -> ExecutionPlan:
        # Get the task
        task = self.core.tasks.get(task_id)
        
        # Build context
        workspace_root = str(self.core.workspace.root())
        workspace_projects = self.core.workspace.list_projects()
        registered_tools = self.core.tools.list_tools()
        
        context = {
            "workspace_root": workspace_root,
            "workspace_projects": workspace_projects,
            "registered_tools": registered_tools
        }
        
        # Build prompt
        prompt = build_planning_prompt(task.title, task.goal, context)
        
        # Call the runtime to get a plan
        response = self.core.runtime.chat(prompt=prompt, profile=capability)
        
        # Parse the plan
        plan = parse_plan_response(task_id, task.goal, response)
        
        # Convert PlanStep to TaskStep and save to task
        try:
            converted_steps = []
            for step in plan.steps:
                task_step = TaskStep(
                    id=step.id,
                    title=step.title,
                    description=step.description,
                    status=TaskStatus.PENDING,  # Set to PENDING enum value
                    tool=step.tool
                )
                converted_steps.append(task_step)
            
            task.steps = converted_steps
            self.core.tasks.save_task(task)
        except Exception as e:
            # If saving fails, we still return the plan
            print(f"Warning: Failed to save steps to task: {e}")
            pass
        
        return plan
