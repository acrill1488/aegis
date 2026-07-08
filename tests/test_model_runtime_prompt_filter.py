from aegis.models.models import ModelRecord
from aegis.models.output_filter import (
    FALLBACK_TEXT,
    IDENTITY_FALLBACK_TEXT,
    clean_model_output,
)
from aegis.models.providers.base import BaseInferenceProvider
from aegis.models.registry import ModelRegistry
from aegis.models.requests import ModelRequest
from aegis.models.results import InferenceResult
from aegis.models.runtime import ModelRuntime


class CapturingProvider(BaseInferenceProvider):
    provider_id = "capture"

    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_request: ModelRequest | None = None

    def generate(self, model_ref: str, request: ModelRequest) -> InferenceResult:
        self.last_request = request
        return InferenceResult(
            success=True,
            task_type=request.task_type,
            provider_id=self.provider_id,
            output={"text": self.response_text},
        )

    def health(self) -> dict:
        return {"provider_id": self.provider_id, "status": "healthy"}


def _runtime(tmp_path, provider: CapturingProvider) -> ModelRuntime:
    registry = ModelRegistry(tmp_path / "registry.json")
    registry.add(
        ModelRecord(
            id="local-general",
            name="Local General",
            provider=provider.provider_id,
            model_ref="local-general",
            task_types=["general", "coding"],
        )
    )
    return ModelRuntime(registry, providers={provider.provider_id: provider})


def test_generate_wraps_prompt_and_filters_output(tmp_path):
    provider = CapturingProvider(
        "Thinking Process:\nsecret\n\nЯ — Qwythos. Финальный ответ."
    )
    runtime = _runtime(tmp_path, provider)

    result = runtime.generate(ModelRequest(task_type="general", input={"prompt": "Расскажи кратко"}))

    assert result.output["text"] == "Финальный ответ."
    assert provider.last_request is not None
    prompt = provider.last_request.input["prompt"]
    assert "You are AEGIS, a local AI co-worker." in prompt
    assert "Project Context:" in prompt
    assert "Do not invent acronyms." in prompt
    assert "User request:\nРасскажи кратко" in prompt


def test_generate_shortcuts_identity_prompt_without_provider_call(tmp_path):
    provider = CapturingProvider("Я — Qwythos.")
    runtime = _runtime(tmp_path, provider)

    result = runtime.generate(ModelRequest(task_type="general", input={"prompt": "Кто ты такой?"}))

    assert result.output["text"] == IDENTITY_FALLBACK_TEXT
    assert provider.last_request is None


def test_generate_adds_profile_message_for_messages(tmp_path):
    provider = CapturingProvider("Готово.")
    runtime = _runtime(tmp_path, provider)

    runtime.generate(
        ModelRequest(
            task_type="coding",
            input={"messages": [{"role": "user", "content": "Исправь код"}]},
        )
    )

    assert provider.last_request is not None
    messages = provider.last_request.input["messages"]
    assert messages[0]["role"] == "system"
    assert "You are AEGIS, a local AI co-worker." in messages[0]["content"]
    assert messages[1]["content"] == "Исправь код"


def test_clean_model_output_removes_think_sections_and_internal_tool_calls():
    text = (
        "preamble</think>\n"
        "<think>hidden</think>\n"
        '```json\n{"tool": "shell", "arguments": {"cmd": "pwd"}}\n```\n'
        "Ответ."
    )

    assert clean_model_output(text) == "Ответ."


def test_clean_model_output_returns_fallback_when_empty():
    assert clean_model_output("<think>hidden</think>") == FALLBACK_TEXT


def test_clean_model_output_returns_identity_shortcut_for_forbidden_identity_only():
    assert clean_model_output("Я — Qwythos...") == IDENTITY_FALLBACK_TEXT


def test_clean_model_output_keeps_answer_after_identity_removal():
    assert clean_model_output("Я — Qwythos... Финальный ответ.") == "Финальный ответ."
