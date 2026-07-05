import json
from typing import Dict, Any

def build_planning_prompt(task_title: str, task_goal: str, context: Dict[str, Any]) -> str:
    prompt = f"""You are an expert AI assistant helping to create execution plans for tasks.
    
Task Title: {task_title}
Task Goal: {task_goal}

Context:
{json.dumps(context, indent=2)}

Please return a strict JSON response with the following structure:
{{"steps": [{{"id": 1, "title": "...", "description": "...", "tool": "filesystem|git|powershell|null"}}]}}
    
The steps should be ordered logically and each step should have:
- id: integer (starting from 1)
- title: brief descriptive title
- description: detailed description of what needs to be done
- tool: one of "filesystem", "git", "powershell", or null

If you cannot create a proper plan, return a single fallback step with the response text as the description.
"""
    return prompt