from typing import List
from aegis.runtime.filters.pipeline import clean_response
from aegis.agent.loop import AgentExecutionLoop
from .web_context import needs_web_context, build_web_context


class BrainEngine:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def ask(self, prompt: str, capability: str = "auto", role: str = "assistant") -> str:
        """Ask a question using the brain engine."""
        # If capability is auto, detect it from the prompt
        if capability == "auto":
            capability = self.core.router.detect(prompt)
        
        # Check if we need web context
        if needs_web_context(prompt):
            # Build web context
            web_context = build_web_context(self.core, prompt)
            
            # Add web context to prompt with specific formatting
            if web_context:
                enhanced_prompt = f"WEB CONTEXT:\n{web_context}\n\nUSER REQUEST:\n{prompt}\n\nIMPORTANT:\nОтветь только на основе WEB CONTEXT.\nНе предлагай использовать инструменты.\nНе выводи JSON tool calls.\nНе описывай план действий.\nДай итоговый ответ на русском."
            else:
                enhanced_prompt = prompt
            
            response = AgentExecutionLoop(self.core).run(enhanced_prompt, capability, role)
        else:
            response = AgentExecutionLoop(self.core).run(prompt, capability, role)
        
        # Apply runtime response pipeline cleaning
        return clean_response(response)
    
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
