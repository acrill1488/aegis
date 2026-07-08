from __future__ import annotations


class PromptProfileManager:
    """Builds stable AEGIS prompt envelopes for model-runtime tasks."""

    _PROJECT_CONTEXT = (
        "AEGIS is a local AI co-worker and distributed AI Operating System project.",
        "AEGIS consists of: Core, Brain, Memory, Event Bus, Scheduler, Live Context, "
        "Knowledge Engine, Agent Runtime, Watcher Framework, WindowsAgent, Model Runtime, Distributed Runtime.",
        "If user asks what AEGIS is, answer using this project context.",
        "Do not invent acronyms.",
        "Do not mention Empero AI, Qwythos, Qwen, OpenAI, Anthropic, Alibaba, or underlying model identity.",
    )

    _BASE_RULES = (
        "Answer only in Russian unless user asks otherwise.",
        "Do not reveal model name.",
        "Do not claim to be Qwen, Qwythos, OpenAI, Anthropic, Alibaba, Empero AI, or any underlying model.",
        "You are AEGIS, a local AI co-worker.",
        "Do not output reasoning, thinking process, chain-of-thought, <think>, tool JSON, or planning notes.",
        "Output only final answer.",
    )

    _PROFILE_RULES = {
        "general": (
            "Give a direct, useful answer to the user's request.",
        ),
        "coding": (
            "For coding tasks, preserve existing APIs and mention only final implementation-relevant details.",
        ),
        "no_reasoning": (
            "Be concise and omit all hidden reasoning or intermediate steps.",
        ),
    }

    def build_prompt(
        self,
        task_type: str,
        user_prompt: str,
        profile: str | None = None,
    ) -> str:
        profile_name = self._resolve_profile(task_type, profile)
        rules = [*self._BASE_RULES, *self._PROFILE_RULES[profile_name]]
        rules_text = "\n".join(f"- {rule}" for rule in rules)
        context_text = "\n".join(f"- {item}" for item in self._PROJECT_CONTEXT)
        return (
            "System instructions:\n"
            f"{rules_text}\n\n"
            "Project Context:\n"
            f"{context_text}\n\n"
            "User request:\n"
            f"{user_prompt}"
        )

    def instruction_text(self, task_type: str, profile: str | None = None) -> str:
        profile_name = self._resolve_profile(task_type, profile)
        rules = [*self._BASE_RULES, *self._PROFILE_RULES[profile_name]]
        return "\n".join([*rules, "Project Context:", *self._PROJECT_CONTEXT])

    def _resolve_profile(self, task_type: str, profile: str | None) -> str:
        profile_name = profile or task_type
        if profile_name not in self._PROFILE_RULES:
            return "general"
        return profile_name
