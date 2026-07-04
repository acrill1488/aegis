from typing import List
from .base import RuntimeProvider
from .ollama import OllamaRuntimeProvider
from ..config.runtime_config import get_runtime_profile
from .postprocess import clean_model_response


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
        # Get the profile configuration
        profile_config = get_runtime_profile(profile)
        
        # If no model is provided, use the one from the profile
        if model is None:
            model = profile_config["model"]
            
        response = self.provider.chat(prompt=prompt, model=model, temperature=temperature, max_tokens=max_tokens)
        return clean_model_response(response)
    
    def is_available(self) -> bool:
        """Check if the runtime is available."""
        return self.provider.is_available()
