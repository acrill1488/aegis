from typing import Dict, Any
from ..context.builder import DEFAULT_PROMPT_BUILDER


class PromptBuilder:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def build(self, user_prompt: str, context: Dict[str, Any], role: str = "assistant") -> str:
        """Build a formatted prompt with system, role, context and user request."""
        # Get memory summary
        try:
            memory_summary = self.core.memory.list_summary()
        except Exception:
            memory_summary = "Память недоступна"
        
        # Build full prompt using the new builder with memory summary
        return DEFAULT_PROMPT_BUILDER.build_prompt(
            workspace_context=context,
            user_prompt=user_prompt,
            memory_summary=memory_summary
        )
