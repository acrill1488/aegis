from aegis.executor.dispatcher import ToolDispatcher
from aegis.task.manager import TaskManager
from aegis.task.status import TaskStatus

class ExecutionEngine:
    def __init__(self, core=None):
        self.dispatcher = ToolDispatcher(core)
        self.task_manager = TaskManager()
    
    def execute_task(self, task_id: str, dry_run: bool = True):
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
        
        # Create sandbox directory if it doesn't exist
        import os
        sandbox_path = r"F:\AI_WORKSPACE\sandbox\executor-test"
        os.makedirs(sandbox_path, exist_ok=True)
        
        # Execute each step
        for i, step in enumerate(task.steps):
            print(f"Executing Step {i+1}: {step.title}")
            
            # Set step status to running
            step.status = TaskStatus.RUNNING
            
            # Save task
            self.task_manager.save_task(task)
            
            # Handle execution based on dry_run flag
            if dry_run:
                # In dry-run mode, we don't actually execute anything
                # Just mark the step as completed with a message
                step.status = TaskStatus.COMPLETED
                step.result = "Dry-run completed"
            else:
                # Real execution mode - use dispatcher
                try:
                    # Set up step kwargs based on tool type and content
                    self._setup_step_kwargs(step)
                    
                    result = self.dispatcher.dispatch(step)
                    
                    # Save result based on success/failure
                    if result.success:
                        step.result = result.stdout
                        step.status = TaskStatus.COMPLETED
                    else:
                        step.result = result.stderr
                        step.status = TaskStatus.FAILED
                except Exception as e:
                    # Handle any errors during tool execution
                    step.result = str(e)
                    step.status = TaskStatus.FAILED
            
            # Save task after each step
            self.task_manager.save_task(task)
        
        # After all steps are done
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.result = "Execution completed"
        
        # Save final task state
        self.task_manager.save_task(task)
    
    def _setup_step_kwargs(self, step):
        """Setup kwargs for different tool types based on step content."""
        if step.tool == "filesystem":
            if "README.md" in step.title or "README.md" in step.description:
                step.action = "write_text"
                step.kwargs = {
                    "path": r"F:\AI_WORKSPACE\sandbox\executor-test\README.md",
                    "content": "# Executor Test\n\nCreated by AEGIS.\n"
                }
            else:
                step.action = "create_dir"
                step.kwargs = {
                    "path": r"F:\AI_WORKSPACE\sandbox\executor-test"
                }
        elif step.tool == "powershell":
            step.action = "safe_run"
            step.kwargs = {
                "command": "python --version"
            }
        elif step.tool == "git":
            step.action = "status"
            step.kwargs = {
                "path": r"F:\AEGIS"
            }
    
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
        
        # Handle execution (always execute, no dry-run for this method)
        try:
            # Set up step kwargs based on tool type and content
            self._setup_step_kwargs(step)
            
            result = self.dispatcher.dispatch(step)
            
            # Save result based on success/failure
            if result.success:
                step.result = result.stdout
                step.status = TaskStatus.COMPLETED
            else:
                step.result = result.stderr
                step.status = TaskStatus.FAILED
        except Exception as e:
            # Handle any errors during tool execution
            step.result = str(e)
            step.status = TaskStatus.FAILED
        
        # Save task after the step
        self.task_manager.save_task(task)
