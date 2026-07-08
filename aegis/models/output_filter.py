from __future__ import annotations

import json
import re


FALLBACK_TEXT = "Не удалось сформировать корректный финальный ответ."
IDENTITY_FALLBACK_TEXT = "Я — AEGIS, локальный AI co-worker пользователя."

_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)
_THINK_END_RE = re.compile(r".*</think>\s*", re.IGNORECASE | re.DOTALL)
_SECTION_START_RE = re.compile(
    r"^\s*(Thinking Process|Reasoning|Chain of thought|Analysis|Step-by-step)\s*[:.].*$",
    re.IGNORECASE,
)
_FENCED_BLOCK_RE = re.compile(r"```(?:json|tool|tools)?\s*\n.*?\n```", re.IGNORECASE | re.DOTALL)
_IDENTITY_REPLACEMENTS = (
    re.compile(r"Я\s*[—-]\s*Qwythos[^\n.。!?…]*[.。!?…]*", re.IGNORECASE),
    re.compile(r"модель\s+создана\s+Empero\s+AI[^\n.。!?…]*[.。!?…]*", re.IGNORECASE),
    re.compile(r"I\s+am\s+Qwythos[^\n.。!?…]*[.。!?…]*", re.IGNORECASE),
    re.compile(r"created\s+by\s+Empero\s+AI[^\n.。!?…]*[.。!?…]*", re.IGNORECASE),
)
_INTERNAL_TOOL_KEYS = {
    "tool",
    "tool_call",
    "tool_calls",
    "function_call",
    "arguments",
    "parameters",
}


def clean_model_output(text: str) -> str:
    cleaned = str(text or "")
    cleaned = _THINK_END_RE.sub("", cleaned)
    cleaned = _THINK_BLOCK_RE.sub("", cleaned)
    cleaned = _remove_internal_fenced_blocks(cleaned)
    cleaned = _remove_internal_json_lines(cleaned)
    cleaned = _remove_reasoning_sections(cleaned)

    identity_removed = False
    for pattern in _IDENTITY_REPLACEMENTS:
        cleaned, removed_count = pattern.subn("", cleaned)
        identity_removed = identity_removed or removed_count > 0

    cleaned = _normalize_blank_lines(cleaned)
    if not cleaned and identity_removed:
        return IDENTITY_FALLBACK_TEXT
    return cleaned if cleaned else FALLBACK_TEXT


def _remove_reasoning_sections(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    skipping = False

    for line in lines:
        if _SECTION_START_RE.match(line):
            skipping = True
            continue
        if skipping:
            if line.strip():
                continue
            skipping = False
            continue
        kept.append(line)

    return "\n".join(kept)


def _remove_internal_fenced_blocks(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        body = re.sub(r"^```(?:json|tool|tools)?\s*|\s*```$", "", block, flags=re.IGNORECASE | re.DOTALL)
        return "" if _looks_like_internal_tool_call(body) else block

    return _FENCED_BLOCK_RE.sub(replace, text)


def _remove_internal_json_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}") and _looks_like_internal_tool_call(stripped):
            continue
        kept.append(line)
    return "\n".join(kept)


def _looks_like_internal_tool_call(value: str) -> bool:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        lowered = value.lower()
        return any(f'"{key}"' in lowered for key in _INTERNAL_TOOL_KEYS) and (
            "call" in lowered or "tool" in lowered or "function" in lowered
        )

    if not isinstance(payload, dict):
        return False
    keys = {str(key).lower() for key in payload}
    return bool(keys & _INTERNAL_TOOL_KEYS) and (
        "tool" in keys
        or "tool_call" in keys
        or "tool_calls" in keys
        or "function_call" in keys
        or {"name", "arguments"} <= keys
    )


def _normalize_blank_lines(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    normalized = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", normalized)
