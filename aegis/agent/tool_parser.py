"""Parse model-emitted tool calls."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def extract_tool_calls(text: str) -> list[dict]:
    """Extract supported tool call formats from model output."""

    calls: list[dict] = []

    for block in _extract_tag_blocks(text):
        calls.extend(_parse_tool_payload(block))

    for block in _extract_json_fences(text):
        calls.extend(_parse_tool_payload(block))

    calls.extend(_extract_dict_like_calls(text))
    return _dedupe_calls(calls)


def _extract_tag_blocks(text: str) -> list[str]:
    blocks = re.findall(
        r"<tool_code>\s*(.*?)\s*</tool_code>",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    blocks.extend(
        re.findall(
            r"<tool>\s*(.*?)\s*</tool>",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
    )
    return blocks


def _extract_json_fences(text: str) -> list[str]:
    pattern = r"```json\s*(.*?)\s*```"
    return re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)


def _extract_dict_like_calls(text: str) -> list[dict]:
    calls: list[dict] = []
    pattern = r"\{[^{}]*(?:['\"](?:name|tool)['\"]\s*:)[\s\S]*?['\"]arguments['\"]\s*:\s*\{[\s\S]*?\}\s*\}"
    for match in re.findall(pattern, text):
        calls.extend(_parse_tool_payload(match))
    return calls


def _parse_tool_payload(payload: str) -> list[dict]:
    payload = payload.strip()
    if not payload:
        return []

    parsed = _loads_payload(payload)
    if parsed is None:
        return []

    if isinstance(parsed, list):
        return [_normalize_call(item) for item in parsed if _normalize_call(item)]

    call = _normalize_call(parsed)
    return [call] if call else []


def _loads_payload(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass

    try:
        return ast.literal_eval(payload)
    except (SyntaxError, ValueError):
        return None


def _normalize_call(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None

    name = value.get("name") or value.get("tool")
    arguments = value.get("arguments") or {}
    if not name:
        return None
    if not isinstance(arguments, dict):
        arguments = {"value": arguments}

    return {
        "name": str(name),
        "arguments": arguments,
    }


def _dedupe_calls(calls: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for call in calls:
        marker = json.dumps(call, sort_keys=True, ensure_ascii=False)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(call)
    return result
