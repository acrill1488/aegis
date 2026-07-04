from abc import ABC, abstractmethod
from typing import List


class RuntimeProvider(ABC):
    """Abstract base class for runtime providers."""
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models."""
        pass
    
    @abstractmethod
    def chat(self, model: str, prompt: str) -> str:
        """Chat with a specific model."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the runtime is available."""
        pass