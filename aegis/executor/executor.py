from aegis.executor.dispatcher import ToolDispatcher
from aegis.task.manager import TaskManager
from aegis.task.status import TaskStatus

class ExecutionEngine:
    def __init__(self):
        self.dispatcher = ToolDispatcher()
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
            
            # Handle execution based on dry_run flag and tool type
            if dry_run:
                # In dry-run mode, we don't actually execute anything
                # Just mark the step as completed with a message
                step.status = TaskStatus.COMPLETED
                step.result = "Dry-run completed"
            else:
                # Real execution mode
                if step.tool == "filesystem":
                    # For filesystem steps, perform safe operations
                    self._execute_filesystem_step(step)
                else:
                    # Skip non-filesystem steps (powershell, git, etc.)
                    step.status = TaskStatus.WAITING
                    step.result = "Skipped: real execution for this tool is not implemented"
            
            # Save task after each step
            self.task_manager.save_task(task)
        
        # After all steps are done
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.result = "Execution completed"
        
        # Save final task state
        self.task_manager.save_task(task)
    
    def _execute_filesystem_step(self, step):
        """Execute a filesystem step safely."""
        # Check if the description mentions creating directories or files
        description = step.description.lower()
        title = step.title.lower() if step.title else ""
        sandbox_path = r"F:\AI_WORKSPACE\sandbox\executor-test"
        
        # Check for directory creation in description or title
        if (("create" in description or "создать" in description) and \
           ("directory" in description or "folder" in description or 
            "папку" in description or "каталог" in description)) or \
           (("create" in title or "создать" in title) and \
           ("directory" in title or "folder" in title or 
            "папку" in title or "каталог" in title)):
            try:
                # Create directory in sandbox
                full_path = os.path.join(sandbox_path, "new_directory")
                os.makedirs(full_path, exist_ok=True)
                step.status = TaskStatus.COMPLETED
                step.result = f"Created directory: {full_path}"
            except Exception as e:
                step.status = TaskStatus.FAILED
                step.result = f"Failed to create directory: {str(e)}"
        elif "readme.md" in description or "readme.md" in title:
            try:
                # Create README.md file in sandbox
                full_path = os.path.join(sandbox_path, "README.md")
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write("# README\n\nThis is a test README file.")
                step.status = TaskStatus.COMPLETED
                step.result = f"Created file: {full_path}"
            except Exception as e:
                step.status = TaskStatus.FAILED
                step.result = f"Failed to create file: {str(e)}"
        else:
            # For other filesystem operations, skip with warning
            step.status = TaskStatus.WAITING
            step.result = "Skipped: not a supported filesystem operation"
    
    def _validate_path_safety(self, path: str) -> bool:
        """Validate that the path is within F:\\AI_WORKSPACE."""
        import os
        # Normalize the path
        normalized_path = os.path.normpath(path)
        # Check if path starts with the sandbox directory
        return normalized_path.startswith(r"F:\AI_WORKSPACE")
    
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
        # Just mark the step as completed with a message
        step.status = TaskStatus.COMPLETED
        step.result = "Dry-run completed"
        
        # Save task after the step
        self.task_manager.save_task(task)
