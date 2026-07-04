from typing import Dict, Any


class PromptBuilder:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def build(self, user_prompt: str, context: Dict[str, Any], role: str = "assistant") -> str:
        """Build a formatted prompt with system, role, context and user request."""
        context_str = "\n".join([f"{key}: {value}" for key, value in context.items()])
        
        return f"""SYSTEM:
You are AEGIS, a local AI co-worker.

ROLE:
{role}

CONTEXT:
{context_str}

USER REQUEST:
{user_prompt}"""