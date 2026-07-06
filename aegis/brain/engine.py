from typing import List

from aegis.agent.loop import AgentExecutionLoop
from aegis.runtime.filters.pipeline import clean_response


FRESH_INFO_MARKERS = (
    "актуаль",
    "текущ",
    "сейчас",
    "сегодня",
    "последн",
    "новост",
    "свеж",
    "latest",
    "current",
    "recent",
    "today",
    "now",
    "news",
)


class BrainEngine:
    def __init__(self, core: "AegisCore"):
        self.core = core

    def ask(self, prompt: str, capability: str = "auto", role: str = "assistant") -> str:
        """Ask a question using the brain engine."""
        if capability == "auto":
            capability = self.core.router.detect(prompt)

        context_bundle = self.core.context_builder.build(prompt)
        if self._requires_web_context(prompt) and self._valid_web_sources_count(context_bundle) == 0:
            return "Не удалось получить содержимое источника. Я не буду делать вывод без данных."

        prompt_context = self.core.context_builder.to_prompt_context(context_bundle)
        enhanced_prompt = f"""{prompt_context}

USER REQUEST:
{prompt}

RULES:
Используй CONTEXT как приоритетный источник.
Если информации в CONTEXT недостаточно, честно скажи.
Если CONTEXT не содержит фактических данных по вопросу — не выдумывай.
Если пользователь просит актуальную/текущую информацию, Brain не имеет права отвечать только из внутренних знаний модели.
Ответь только финальным ответом на русском."""

        response = AgentExecutionLoop(self.core).run(enhanced_prompt, capability, role)
        return clean_response(response)

    def summarize_task(self, task_id: str) -> str:
        """Summarize a task."""
        task = self.core.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        summary = f"""
Task Summary for {task.title}
Goal: {task.goal}
Status: {task.status}
Progress: {task.progress}
Result: {task.result}
Steps: {', '.join(task.steps) if task.steps else 'None'}
        """

        return summary.strip()

    def remember(self, title: str, content: str, tags: List[str] | None = None) -> None:
        """Remember information in the brain."""
        self.core.memory.add(
            type="brain",
            title=title,
            content=content,
            tags=tags or [],
        )

    def _requires_web_context(self, prompt: str) -> bool:
        normalized = prompt.lower()
        return (
            self.core.knowledge.web_provider.has_urls(prompt)
            or any(marker in normalized for marker in FRESH_INFO_MARKERS)
        )

    def _valid_web_sources_count(self, context_bundle) -> int:
        return sum(
            1
            for source in context_bundle.sources
            if source.type == "web"
            and source.score > 0.0
            and not source.metadata.get("invalid")
            and source.content.strip()
        )
