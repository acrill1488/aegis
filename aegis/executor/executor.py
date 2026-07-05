from aegis.executor.dispatcher import ToolDispatcher
from aegis.task.manager import TaskManager
from aegis.task.status import TaskStatus

class ExecutionEngine:
    def __init__(self):
        self.dispatcher = ToolDispatcher()
        self.task_manager = TaskManager()
    
    def execute_task(self, task_id: str):
        """Execute a task by walking through its steps."""
        # Get the task
        task = self.task_manager.get(task_id)
        if not task:
            print(f"Error: Task with id {task_id} not found")
            return
        
        # Check if task has steps
        if not task.steps:
            print("No steps to execute")
            return
        
        # Execute each step
        for i, step in enumerate(task.steps):
            print(f"Executing Step {i+1}: {step.title}")
            
            # Set step status to running
            step.status = TaskStatus.RUNNING
            
            # Save task
            self.task_manager.save_task(task)
            
            # In dry-run mode, we don't actually execute anything
            # Just mark the step as completed
            step.status = TaskStatus.COMPLETED
            step.result = "Dry-run completed"
            
            # Save task after each step
            self.task_manager.save_task(task)
        
        # After all steps are done
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.result = "Execution dry-run completed"
        
        # Save final task state
        self.task_manager.save_task(task)
    
    def execute_step(self, task_id: str, step_id: str):
        """Execute a specific step of a task."""
        # Get the task
        task = self.task_manager.get(task_id)
        if not task:
            print(f"Error: Task with id {task_id} not found")
            return
        
        # Find the specific step
        step = None
        for s in task.steps:
            if str(s.id) == str(step_id):
                step = s
                break
        
        if not step:
            print(f"Error: Step with id {step_id} not found in task {task_id}")
            return
        
        print(f"Executing Step {step_id}: {step.title}")
        
        # Set step status to running
        step.status = TaskStatus.RUNNING
        
        # Save task
        self.task_manager.save_task(task)
        
        # In dry-run mode, we don't actually execute anything
        # Just mark the step as completed
        step.status = TaskStatus.COMPLETED
        step.result = "Dry-run completed"
        
        # Save task after the step
        self.task_manager.save_task(task)
