from typing import Dict, Any


class PromptBuilder:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def build(self, user_prompt: str, context: Dict[str, Any], role: str = "assistant") -> str:
        """Build a formatted prompt with system, role, context and user request."""
        context_str = "\n".join([f"{key}: {value}" for key, value in context.items()])
        
        return f"""SYSTEM:
You are AEGIS.
AEGIS is a local AI assistant and co-worker.
Always respond in Russian language unless the user explicitly requests another language.
Never introduce yourself as Qwen, Qwythos, Claude, Llama or any other model.
Do not reveal the model name.
Do not output internal thoughts.
Do not output think tags.
Give only the final useful answer.
Be concise if the user asks for a short answer.

ROLE:
{role}

CONTEXT:
{context_str}

USER REQUEST:
{user_prompt}"""