import httpx
from typing import List
from .base import RuntimeProvider
from aegis.config.services import get_service_base_url


class OllamaRuntimeProvider(RuntimeProvider):
    """Runtime provider for Ollama."""
    
    def __init__(self, base_url: str | None = None, model: str = None, timeout: int = 30):
        self.base_url = get_service_base_url("ollama", explicit=base_url)
        self.default_model = model
        self.timeout = timeout
    
    def list_models(self) -> List[str]:
        """List available models from Ollama."""
        url = f"{self.base_url.rstrip('/')}/api/tags"
        r = httpx.get(url, timeout=self.timeout, trust_env=False)
        if r.status_code != 200:
            return []
        data = r.json()
        return [m["name"] for m in data.get("models", []) if "name" in m]
    
    def chat(self, prompt: str, model: str | None = None, timeout: int | None = None, temperature: float | None = None, max_tokens: int | None = None) -> str:
        """Chat with a specific model."""
        # Use the provided model or default model if none specified
        selected_model = model or self.default_model
        
        try:
            payload = {
                "model": selected_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens or 4096,
                    "temperature": temperature or 0.4
                }
            }
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=timeout or self.timeout,
                trust_env=False
            )
            if response.status_code != 200:
                return f"Error: HTTP {response.status_code}"
            
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            return f"Error: {str(e)}"
    
    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=self.timeout, trust_env=False)
            # If we get a 200 status, the runtime is available
            return r.status_code == 200
        except Exception:
            return False
