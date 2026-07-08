from aegis.models.models import ModelRecord
from aegis.models.providers.base import BaseInferenceProvider
from aegis.models.registry import ModelRegistry
from aegis.models.router import ModelRouter


class FakeProvider(BaseInferenceProvider):
    def __init__(self, provider_id: str, status: str):
        self.provider_id = provider_id
        self.status = status

    def health(self) -> dict:
        return {"provider_id": self.provider_id, "status": self.status}


def _registry(tmp_path) -> ModelRegistry:
    return ModelRegistry(tmp_path / "registry.json")


def _add_models(registry: ModelRegistry) -> None:
    registry.add(
        ModelRecord(
            id="balanced-small",
            name="Balanced Small",
            provider="healthy",
            model_ref="balanced-small",
            task_types=["coding"],
            context_window=32768,
            input_modalities=["text"],
            output_modalities=["text"],
            vram_required_gb=8,
            quality_tier="B",
            speed_tier="fast",
        )
    )
    registry.add(
        ModelRecord(
            id="quality-large",
            name="Quality Large",
            provider="healthy",
            model_ref="quality-large",
            task_types=["coding"],
            context_window=65536,
            input_modalities=["text"],
            output_modalities=["text"],
            vram_required_gb=24,
            quality_tier="A",
            speed_tier="balanced",
        )
    )
    registry.add(
        ModelRecord(
            id="quality-smaller",
            name="Quality Smaller",
            provider="healthy",
            model_ref="quality-smaller",
            task_types=["coding"],
            context_window=65536,
            input_modalities=["text"],
            output_modalities=["text"],
            vram_required_gb=16,
            quality_tier="A",
            speed_tier="balanced",
        )
    )
    registry.add(
        ModelRecord(
            id="unhealthy-best",
            name="Unhealthy Best",
            provider="unhealthy",
            model_ref="unhealthy-best",
            task_types=["coding"],
            context_window=131072,
            input_modalities=["text"],
            output_modalities=["text"],
            quality_tier="S",
            speed_tier="fast",
        )
    )


def test_select_filters_unhealthy_provider_and_ranks_candidates(tmp_path):
    registry = _registry(tmp_path)
    _add_models(registry)
    router = ModelRouter(
        registry,
        providers={
            "healthy": FakeProvider("healthy", "healthy"),
            "unhealthy": FakeProvider("unhealthy", "unhealthy"),
        },
    )

    selected = router.select("coding")

    assert selected is not None
    assert selected.id == "quality-smaller"


def test_select_applies_constraints(tmp_path):
    registry = _registry(tmp_path)
    _add_models(registry)
    router = ModelRouter(
        registry,
        providers={"healthy": FakeProvider("healthy", "healthy")},
    )

    selected = router.select(
        "coding",
        constraints={
            "provider": "healthy",
            "min_context_window": 65536,
            "quality_tier": "A",
            "speed_tier": "balanced",
            "input_modalities": ["text"],
            "output_modalities": ["text"],
        },
    )

    assert selected is not None
    assert selected.id == "quality-smaller"


def test_candidates_can_include_disabled_models(tmp_path):
    registry = _registry(tmp_path)
    registry.add(
        ModelRecord(
            id="disabled",
            name="Disabled",
            provider="healthy",
            model_ref="disabled",
            task_types=["general"],
            enabled=False,
        )
    )
    router = ModelRouter(registry)

    assert router.candidates("general") == []
    assert [record.id for record in router.candidates("general", enabled_only=False)] == [
        "disabled"
    ]
