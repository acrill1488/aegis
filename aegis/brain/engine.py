from typing import List


class BrainEngine:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def ask(self, prompt: str, capability: str = "auto", role: str = "assistant") -> str:
        """Ask a question using the brain engine."""
        # If capability is auto, detect it from the prompt
        if capability == "auto":
            capability = self.core.router.detect(prompt)
        
        # Run the agent
        response = self.core.agent.run(prompt, capability, role)
        
        return response
    
    def summarize_task(self, task_id: str) -> str:
        """Summarize a task."""
        task = self.core.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Create summary
        summary = f"""
Task Summary for {task.title}
Goal: {task.goal}
Status: {task.status}
Progress: {task.progress}
Result: {task.result}
Steps: {', '.join(task.steps) if task.steps else 'None'}
        """
        
        return summary.strip()
    
    def remember(self, title: str, content: str, tags: List[str] | None = None) -> None:
        """Remember information in the brain."""
        # Add to memory
        self.core.memory.add(
            type="brain",
            title=title,
            content=content,
            tags=tags or []
        )