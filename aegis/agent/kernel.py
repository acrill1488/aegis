from .context import ContextBuilder
from .prompts import PromptBuilder
from aegis.context.builder import DEFAULT_PROMPT_BUILDER
from aegis.prompt import render_prompt_package


class AgentKernel:
    def __init__(self, core: 'AegisCore'):
        self.core = core
        # Set up the prompt builder with memory manager
        DEFAULT_PROMPT_BUILDER.set_memory_manager(self.core.memory)
    
    def run(self, prompt: str, capability: str = "general", role: str = "assistant") -> str:
        """Run an agent with the given prompt and capability."""
        return self.core.runtime.chat(
            prompt=self._compile_prompt(prompt, capability, role),
            profile=self._resolve_capability(prompt, capability),
            model=None,
        )

    def run_raw(self, prompt: str, capability: str = "general", role: str = "assistant") -> str:
        """Run an agent and return raw model output before response cleanup."""
        resolved_capability = self._resolve_capability(prompt, capability)
        full_prompt = self._compile_prompt(prompt, resolved_capability, role)
        if hasattr(self.core.runtime, "chat_raw"):
            return self.core.runtime.chat_raw(
                prompt=full_prompt,
                profile=resolved_capability,
                model=None,
            )
        return self.core.runtime.chat(prompt=full_prompt, profile=resolved_capability, model=None)

    def _resolve_capability(self, prompt: str, capability: str) -> str:
        # If capability is auto, detect it from the prompt
        if capability == "auto":
            return self.core.router.detect(prompt)
        return capability

    def _compile_prompt(self, prompt: str, capability: str, role: str) -> str:
        # Build context
        context_builder = ContextBuilder(self.core)
        context = context_builder.build()
        
        # Compile prompt before sending it to runtime.
        prompt_package = PromptBuilder(self.core).compile(prompt, context, role)
        full_prompt = render_prompt_package(prompt_package)
        
        return full_prompt
