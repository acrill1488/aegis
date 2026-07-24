"""Stable errors for the embedding vertical."""


class EmbeddingError(RuntimeError):
    code = "embeddings.provider.failed"


class EmbeddingValidationError(EmbeddingError):
    code = "embeddings.validation.failed"


class EmbeddingProviderMissingError(EmbeddingError):
    code = "embeddings.provider.missing"


class EmbeddingProviderDisabledError(EmbeddingError):
    code = "embeddings.provider.disabled"


class EmbeddingInitializationError(EmbeddingError):
    code = "embeddings.model.initialization_failed"


class EmbeddingTimeoutError(EmbeddingError):
    code = "embeddings.timeout"


class EmbeddingDimensionError(EmbeddingError):
    code = "embeddings.dimension_mismatch"

