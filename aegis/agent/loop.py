"""Agent execution loop with Response Protocol parsing."""

from __future__ import annotations

from aegis.protocol import ProtocolParser
from aegis.runtime.filters.pipeline import clean_response

from .tool_executor import AgentToolExecutor


class AgentExecutionLoop:
    """Run Prompt -> LLM -> Protocol Parser -> Tools -> LLM -> User."""

    def __init__(self, core):
        self.core = core
        self.tool_executor = AgentToolExecutor(core)
        self.parser = ProtocolParser()

    def run(
        self,
        prompt: str,
        capability: str = "auto",
        role: str = "assistant",
    ) -> str:
        if capability == "auto":
            capability = self.core.router.detect(prompt)

        raw_output = self.core.agent.run_raw(prompt, capability, role)
        response = self.parser.parse(raw_output)
        if not response.tool_calls:
            return self._finalize(raw_output)

        tool_results = []
        for index, tool_call in enumerate(response.tool_calls, start=1):
            result = self.tool_executor.execute(tool_call)
            name = tool_call.get("name") or tool_call.get("tool") or "unknown"
            tool_results.append(f"[{index}] {name}\n{result}")

        follow_up_prompt = f"""USER REQUEST:
{prompt}

TOOL RESULTS:
{chr(10).join(tool_results)}

IMPORTANT:
Заверши ответ строкой:
FINAL:
После FINAL напиши только итоговый ответ пользователю на русском.
Не показывай reasoning.
Не показывай tool calls.
Не выводи JSON.
"""

        final_output = self.core.agent.run_raw(follow_up_prompt, capability, role)
        return self._finalize(final_output)

    def _finalize(self, raw_output: str) -> str:
        response = self.parser.parse(raw_output)
        return clean_response(response.final_answer)
