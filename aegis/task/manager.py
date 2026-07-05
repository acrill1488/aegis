import json
import os
from datetime import datetime
from typing import List, Optional
from .models import AegisTask, TaskStep
from .status import TaskStatus, TaskPriority

# Define the tasks storage path
TASKS_STORAGE_PATH = "F:\\AI_WORKSPACE\\tasks\\tasks.json"

class TaskManager:
    def __init__(self):
        # Ensure the directory exists
        os.makedirs(os.path.dirname(TASKS_STORAGE_PATH), exist_ok=True)
        
        # Initialize tasks storage
        if not os.path.exists(TASKS_STORAGE_PATH):
            self._tasks = []
            self._save_tasks()
        else:
            with open(TASKS_STORAGE_PATH, 'r', encoding='utf-8') as f:
                self._tasks = json.load(f)
    
    def _save_tasks(self) -> None:
        """Save tasks to JSON file."""
        with open(TASKS_STORAGE_PATH, 'w', encoding='utf-8') as f:
            json.dump(self._tasks, f, ensure_ascii=False, indent=2, default=str)
    
    def create(self, title: str, goal: str, priority: TaskPriority = TaskPriority.NORMAL, 
              session_id: Optional[str] = None, parent_id: Optional[str] = None) -> AegisTask:
        """Create a new task."""
        # Generate a unique ID (in a real implementation this would be more robust)
        import uuid
        task_id = str(uuid.uuid4())
        
        task = AegisTask(
            id=task_id,
            title=title,
            goal=goal,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status=TaskStatus.PENDING,
            priority=priority,
            session_id=session_id,
            parent_id=parent_id
        )
        
        # Convert to dict for JSON storage
        task_dict = {
            "id": task.id,
            "title": task.title,
            "goal": task.goal,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "status": task.status.value,
            "priority": task.priority.value,
            "session_id": task.session_id,
            "parent_id": task.parent_id,
            "steps": [],
            "progress": task.progress,
            "result": task.result,
            "metadata": task.metadata
        }
        
        self._tasks.append(task_dict)
        self._save_tasks()
        return task
    
    def get(self, task_id: str) -> Optional[AegisTask]:
        """Get a task by ID."""
        for task_dict in self._tasks:
            if task_dict["id"] == task_id:
                # Convert JSON steps to TaskStep objects
                steps = []
                if "steps" in task_dict and task_dict["steps"]:
                    for step_dict in task_dict["steps"]:
                        # Handle status conversion - if it's a string, convert to TaskStatus enum
                        status = step_dict.get("status", "pending")
                        if isinstance(status, str):
                            status = TaskStatus(status)
                        else:
                            status = TaskStatus.PENDING  # default fallback
                        
                        step = TaskStep(
                            id=step_dict["id"],
                            title=step_dict["title"],
                            description=step_dict["description"],
                            status=status,
                            tool=step_dict.get("tool"),
                            result=step_dict.get("result")
                        )
                        steps.append(step)
                
                # Convert back to AegisTask object
                task = AegisTask(
                    id=task_dict["id"],
                    title=task_dict["title"],
                    goal=task_dict["goal"],
                    created_at=datetime.fromisoformat(task_dict["created_at"]),
                    updated_at=datetime.fromisoformat(task_dict["updated_at"]),
                    status=TaskStatus(task_dict["status"]),
                    priority=TaskPriority(task_dict["priority"]),
                    session_id=task_dict["session_id"],
                    parent_id=task_dict["parent_id"],
                    steps=steps,
                    progress=task_dict["progress"],
                    result=task_dict["result"],
                    metadata=task_dict["metadata"]
                )
                return task
        return None
    
    def list_tasks(self) -> List[AegisTask]:
        """List all tasks."""
        tasks = []
        for task_dict in self._tasks:
            task = AegisTask(
                id=task_dict["id"],
                title=task_dict["title"],
                goal=task_dict["goal"],
                created_at=datetime.fromisoformat(task_dict["created_at"]),
                updated_at=datetime.fromisoformat(task_dict["updated_at"]),
                status=TaskStatus(task_dict["status"]),
                priority=TaskPriority(task_dict["priority"]),
                session_id=task_dict["session_id"],
                parent_id=task_dict["parent_id"],
                steps=[],
                progress=task_dict["progress"],
                result=task_dict["result"],
                metadata=task_dict["metadata"]
            )
            tasks.append(task)
        return tasks
    
    def update_status(self, task_id: str, status: TaskStatus) -> Optional[AegisTask]:
        """Update task status."""
        for task_dict in self._tasks:
            if task_dict["id"] == task_id:
                task_dict["status"] = status.value
                task_dict["updated_at"] = datetime.now().isoformat()
                self._save_tasks()
                
                # Return the updated task
                task = AegisTask(
                    id=task_dict["id"],
                    title=task_dict["title"],
                    goal=task_dict["goal"],
                    created_at=datetime.fromisoformat(task_dict["created_at"]),
                    updated_at=datetime.fromisoformat(task_dict["updated_at"]),
                    status=TaskStatus(task_dict["status"]),
                    priority=TaskPriority(task_dict["priority"]),
                    session_id=task_dict["session_id"],
                    parent_id=task_dict["parent_id"],
                    steps=[],
                    progress=task_dict["progress"],
                    result=task_dict["result"],
                    metadata=task_dict["metadata"]
                )
                return task
        return None
    
    def set_result(self, task_id: str, result: str) -> Optional[AegisTask]:
        """Set task result."""
        for task_dict in self._tasks:
            if task_dict["id"] == task_id:
                task_dict["result"] = result
                task_dict["status"] = TaskStatus.COMPLETED.value  # Set status to COMPLETED when result is set
                task_dict["updated_at"] = datetime.now().isoformat()
                self._save_tasks()
                
                # Return the updated task
                task = AegisTask(
                    id=task_dict["id"],
                    title=task_dict["title"],
                    goal=task_dict["goal"],
                    created_at=datetime.fromisoformat(task_dict["created_at"]),
                    updated_at=datetime.fromisoformat(task_dict["updated_at"]),
                    status=TaskStatus(task_dict["status"]),
                    priority=TaskPriority(task_dict["priority"]),
                    session_id=task_dict["session_id"],
                    parent_id=task_dict["parent_id"],
                    steps=[],
                    progress=task_dict["progress"],
                    result=task_dict["result"],
                    metadata=task_dict["metadata"]
                )
                return task
        return None
    
    def cancel(self, task_id: str) -> Optional[AegisTask]:
        """Cancel a task."""
        for task_dict in self._tasks:
            if task_dict["id"] == task_id:
                task_dict["status"] = TaskStatus.CANCELLED.value
                task_dict["updated_at"] = datetime.now().isoformat()
                self._save_tasks()
                
                # Return the updated task
                task = AegisTask(
                    id=task_dict["id"],
                    title=task_dict["title"],
                    goal=task_dict["goal"],
                    created_at=datetime.fromisoformat(task_dict["created_at"]),
                    updated_at=datetime.fromisoformat(task_dict["updated_at"]),
                    status=TaskStatus(task_dict["status"]),
                    priority=TaskPriority(task_dict["priority"]),
                    session_id=task_dict["session_id"],
                    parent_id=task_dict["parent_id"],
                    steps=[],
                    progress=task_dict["progress"],
                    result=task_dict["result"],
                    metadata=task_dict["metadata"]
                )
                return task
        return None
    
    def save_task(self, task: AegisTask) -> None:
        """Save a task to storage."""
        # Find the existing task in our list
        for i, task_dict in enumerate(self._tasks):
            if task_dict["id"] == task.id:
                # Convert AegisTask back to dict format
                task_dict = {
                    "id": task.id,
                    "title": task.title,
                    "goal": task.goal,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "session_id": task.session_id,
                    "parent_id": task.parent_id,
                    "steps": [
                        {
                            "id": step.id,
                            "title": step.title,
                            "description": step.description,
                            "status": step.status.value,
                            "tool": step.tool,
                            "result": step.result
                        } for step in task.steps
                    ],
                    "progress": task.progress,
                    "result": task.result,
                    "metadata": task.metadata
                }
                self._tasks[i] = task_dict
                self._save_tasks()
                return
        # If we get here, the task wasn't found (shouldn't happen in normal usage)
        raise ValueError(f"Task with id {task.id} not found in storage")
