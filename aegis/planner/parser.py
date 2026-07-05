import json
import re
from typing import Dict, Any
from aegis.planner.models import ExecutionPlan, PlanStep

def parse_plan_response(task_id: str, goal: str, response: str) -> ExecutionPlan:
    # Try to find JSON in the response
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            steps_data = data.get("steps", [])
            
            # Convert steps data to PlanStep objects
            steps = []
            for step_data in steps_data:
                step = PlanStep(
                    id=step_data.get("id"),
                    title=step_data.get("title", ""),
                    description=step_data.get("description", ""),
                    tool=step_data.get("tool")
                )
                steps.append(step)
            
            return ExecutionPlan(
                task_id=task_id,
                goal=goal,
                steps=steps,
                raw_response=response
            )
        except json.JSONDecodeError:
            # If JSON parsing fails, create a fallback step
            pass
    
    # If no valid JSON found or parsing failed, create a single fallback step
    fallback_step = PlanStep(
        id=1,
        title="Fallback Step",
        description=response.strip(),
        tool=None
    )
    
    return ExecutionPlan(
        task_id=task_id,
        goal=goal,
        steps=[fallback_step],
        raw_response=response
    )