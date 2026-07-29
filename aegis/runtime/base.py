from abc import ABC, abstractmethod
from collections.abc import Iterator
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

    def health(self) -> dict:
        """Return provider health details without changing availability semantics."""
        return {"available": self.is_available()}

    def stream_chat(self, *args, **kwargs) -> Iterator[str]:
        """Stream chat output, with a compatibility fallback for older providers."""
        yield self.chat(*args, **kwargs)
