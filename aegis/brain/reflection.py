class ReflectionEngine:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def reflect_task(self, task_id: str) -> str:
        """Reflect on a task and return a summary."""
        # Get the task
        task = self.core.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Build steps text
        if task.steps:
            steps_text = "\n".join([
                f"- Step {step.id}: {step.title} | status={step.status.value} | tool={step.tool} | result={step.result}"
                for step in task.steps
            ])
        else:
            steps_text = "None"
        
        # Build summary
        summary = f"""
Reflection for Task: {task.title}
Goal: {task.goal}
Status: {task.status.value}
Progress: {task.progress}
Result: {task.result}
Steps: 
{steps_text}
        """
        
        # Save reflection to memory
        self.core.memory.add(
            type="reflection",
            title=f"Task reflection: {task.title}",
            content=summary,
            tags=["task", "reflection", "aegis"]
        )
        
        return summary.strip()
