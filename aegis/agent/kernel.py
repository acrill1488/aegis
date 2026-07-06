from .context import ContextBuilder
from .prompts import PromptBuilder


class AgentKernel:
    def __init__(self, core: 'AegisCore'):
        self.core = core
    
    def run(self, prompt: str, capability: str = "general", role: str = "assistant") -> str:
        """Run an agent with the given prompt and capability."""
        # If capability is auto, detect it from the prompt
        if capability == "auto":
            capability = self.core.router.detect(prompt)
        
        # Build context
        context_builder = ContextBuilder(self.core)
        context = context_builder.build()
        
        # Build full prompt
        prompt_builder = PromptBuilder(self.core)
        full_prompt = prompt_builder.build(prompt, context, role)
        
        # Send to core runtime
        response = self.core.runtime.chat(prompt=full_prompt, profile=capability, model=None)
        
        return response
