from .context import ContextBuilder
from .prompts import PromptBuilder
from aegis.context.builder import DEFAULT_PROMPT_BUILDER


class AgentKernel:
    def __init__(self, core: 'AegisCore'):
        self.core = core
        # Set up the prompt builder with memory manager
        DEFAULT_PROMPT_BUILDER.set_memory_manager(self.core.memory)
    
    def run(self, prompt: str, capability: str = "general", role: str = "assistant") -> str:
        """Run an agent with the given prompt and capability."""
        # If capability is auto, detect it from the prompt
        if capability == "auto":
            capability = self.core.router.detect(prompt)
        
        # Build context
        context_builder = ContextBuilder(self.core)
        context = context_builder.build()
        
        # Build full prompt
        full_prompt = DEFAULT_PROMPT_BUILDER.build_prompt(context, prompt)
        
        # Send to core runtime
        response = self.core.runtime.chat(prompt=full_prompt, profile=capability, model=None)
        
        return response
