"""Read-only tool execution helpers for the agent loop."""

from __future__ import annotations

from typing import Any


class AgentToolExecutor:
    """Execute a small allowlist of agent tool calls."""

    def __init__(self, core):
        self.core = core

    def execute(self, tool_call: dict) -> str:
        name = str(tool_call.get("name") or tool_call.get("tool") or "").strip()
        arguments = tool_call.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}

        normalized = name.lower()
        if normalized == "memory":
            return self._execute_memory(arguments)
        if normalized in {"web", "browser"}:
            return self._execute_web(arguments)
        return f"Tool not available: {name}"

    def _execute_memory(self, arguments: dict[str, Any]) -> str:
        query = arguments.get("key") or arguments.get("query")
        if not query:
            return "Memory query is empty."

        records = self.core.memory.search(str(query))
        if not records:
            return "Memory: no matching records."

        lines = ["Memory results:"]
        for record in records:
            content = record.content[:500]
            lines.append(f"- {record.title} ({record.type}): {content}")
        return "\n".join(lines)

    def _execute_web(self, arguments: dict[str, Any]) -> str:
        url = arguments.get("url")
        if not url:
            return "Web URL is empty."

        result = self.core.web.fetch_url(str(url))
        if result.get("error"):
            return f"Web error: {result['error']}"

        title = result.get("title") or "Untitled"
        preview = result.get("text_preview") or ""
        return f"Web result:\nTitle: {title}\nPreview:\n{preview[:1500]}"
