"""Provider-local exports of stable embedding errors."""

from aegis.embeddings.errors import (
    EmbeddingDimensionError,
    EmbeddingInitializationError,
    EmbeddingProviderDisabledError,
    EmbeddingProviderMissingError,
    EmbeddingTimeoutError,
)

__all__ = [
    "EmbeddingDimensionError", "EmbeddingInitializationError", "EmbeddingProviderDisabledError",
    "EmbeddingProviderMissingError", "EmbeddingTimeoutError",
]

