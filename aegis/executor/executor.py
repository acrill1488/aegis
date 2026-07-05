from aegis.executor.dispatcher import ToolDispatcher

class ExecutionEngine:
    def __init__(self):
        self.dispatcher = ToolDispatcher()
    
    def execute_task(self, task_id: str):
        """Execute a task by walking through its steps."""
        # For now, we'll just print the execution steps
        print(f"Executing task {task_id}")
        
    def execute_step(self, task_id: str, step_id: str):
        """Execute a specific step of a task."""
        print(f"Executing Step {step_id} for task {task_id}")
        # For now, just call the dispatcher
        return self.dispatcher.dispatch(step_id)