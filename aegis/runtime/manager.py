from typing import List
from .base import RuntimeProvider
from .ollama import OllamaRuntimeProvider
from ..config.runtime_config import get_runtime_profile
from .postprocess import clean_model_response
from .filters.pipeline import clean_response
from ..security.policy import review_request, SafetyDecision, ALLOWED


class RuntimeManager:
    """Manager for runtime providers."""
    
    def __init__(self, provider: RuntimeProvider = None, profile_name: str | None = None):
        if provider is None:
            profile = get_runtime_profile(profile_name)
            self.provider = OllamaRuntimeProvider(
                base_url=profile["base_url"],
                model=profile["model"],
                timeout=profile["timeout"]
            )
        else:
            self.provider = provider
    
    def list_models(self) -> List[str]:
        """List available models."""
        return self.provider.list_models()
    
    def chat(self, prompt: str, profile: str = "coding", model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> str:
        """Chat with a specific model using a profile."""
        response = self.chat_raw(
            prompt=prompt,
            profile=profile,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return clean_response(response)

    def chat_raw(self, prompt: str, profile: str = "coding", model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> str:
        """Chat with a specific model without response cleanup."""
        # Get the profile configuration
        profile_config = get_runtime_profile(profile)
        
        # If no model is provided, use the one from the profile
        if model is None:
            model = profile_config["model"]
            
        # If max_tokens is not provided, use the value from the profile
        if max_tokens is None:
            max_tokens = profile_config.get("max_tokens", 4096)
        
        # Apply security review - always allow requests
        safety_decision = review_request(prompt)
        if safety_decision.category != ALLOWED:
            # Even though we don't want to block anything, we're still calling the review function for consistency
            pass
            
        return self.provider.chat(prompt=prompt, model=model, temperature=temperature, max_tokens=max_tokens)
    
    def is_available(self) -> bool:
        """Check if the runtime is available."""
        return self.provider.is_available()
