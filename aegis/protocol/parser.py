"""Response Protocol v1 parser."""

from __future__ import annotations

import ast
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from aegis.runtime.filters.pipeline import clean_response

from .contracts import ResponseContract


class ProtocolParser:
    """Parse protocol output into a ResponseContract."""

    INVALID_FINAL = "Не удалось сформировать корректный финальный ответ."
    REASONING_PREFIXES = (
        "The user",
        "I need",
        "I should",
        "I will",
        "I’ll",
        "I'll",
        "Before answering",
        "Since the user",
        "The system",
        "This suggests",
        "I can",
        "I must",
        "Given",
        "Therefore",
        "Thus",
    )

    def parse(self, text: str) -> ResponseContract:
        final = self._extract_final(text)
        tool_calls = self._extract_tools(text)
        citations = self._extract_citations(text)

        if final is None:
            final = self._fallback_final(text)
        final = self._ensure_final(final)

        return ResponseContract(
            thought=self._extract_thought(text),
            tool_calls=tool_calls,
            final_answer=final,
            citations=citations,
            metadata={
                "protocol": "response-protocol-v1",
                "has_final": bool(final),
                "tool_count": len(tool_calls),
            },
        )

    def final_answer(self, text: str) -> str:
        """Return only the final user-facing answer."""

        return self.parse(text).final_answer

    def _extract_final(self, text: str) -> str | None:
        marker_final = self._extract_marker_final(text)
        if marker_final is not None:
            return marker_final

        match = re.search(r"<final>\s*(.*?)\s*</final>", text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return clean_response(match.group(1)).strip()

        root = self._parse_xml_payload(text)
        if root is not None:
            node = root.find(".//final")
            if node is not None and node.text:
                return clean_response(node.text).strip()

        return None

    def _extract_marker_final(self, text: str) -> str | None:
        matches = list(re.finditer(r"FINAL\s*:", text, flags=re.IGNORECASE))
        if not matches:
            return None
        final_text = text[matches[-1].end():]
        return clean_response(final_text).strip()

    def _extract_tools(self, text: str) -> list[dict]:
        calls: list[dict] = []

        for block in re.findall(r"<tool>\s*(.*?)\s*</tool>", text, flags=re.DOTALL | re.IGNORECASE):
            calls.extend(self._parse_tool_block(block))

        parsed = self._parse_json_payload(text)
        if isinstance(parsed, dict):
            calls.extend(self._tools_from_dict(parsed))

        root = self._parse_xml_payload(text)
        if root is not None:
            for node in root.findall(".//tool"):
                content = "".join(node.itertext()).strip()
                calls.extend(self._parse_tool_block(content))

        return self._dedupe(calls)

    def _extract_citations(self, text: str) -> list:
        parsed = self._parse_json_payload(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("citations"), list):
            return parsed["citations"]
        return []

    def _extract_thought(self, text: str) -> str | None:
        match = re.search(r"<thought>\s*(.*?)\s*</thought>", text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _fallback_final(self, text: str) -> str:
        cleaned = clean_response(text)
        cleaned = re.sub(r"</?response>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<tool>\s*.*?\s*</tool>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = self._strip_leading_reasoning(cleaned)
        if not cleaned.strip():
            cleaned = self._fallback_from_raw(text)
        return cleaned.strip()

    def _fallback_from_raw(self, text: str) -> str:
        cleaned = re.sub(r"<think>\s*.*?\s*</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"</?think>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<tool_code>\s*.*?\s*</tool_code>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<tool>\s*.*?\s*</tool>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"</?response>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"```json\s*.*?\s*```", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = self._strip_leading_reasoning(cleaned)
        return clean_response(cleaned).strip()

    def _strip_leading_reasoning(self, text: str) -> str:
        lines = text.splitlines()
        index = 0

        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue
            if self._is_reasoning_start(stripped):
                index += 1
                continue
            break

        return "\n".join(lines[index:]).strip()

    def _is_reasoning_start(self, line: str) -> bool:
        return line.startswith(self.REASONING_PREFIXES)

    def _ensure_final(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned or cleaned.strip(". \n\t") == "":
            return self.INVALID_FINAL
        return cleaned

    def _parse_tool_block(self, block: str) -> list[dict]:
        parsed = self._loads(block.strip())
        if isinstance(parsed, list):
            return [call for item in parsed if (call := self._normalize_tool(item))]
        if isinstance(parsed, dict):
            if "tool_calls" in parsed and isinstance(parsed["tool_calls"], list):
                return [call for item in parsed["tool_calls"] if (call := self._normalize_tool(item))]
            call = self._normalize_tool(parsed)
            return [call] if call else []
        return []

    def _tools_from_dict(self, value: dict) -> list[dict]:
        if isinstance(value.get("tool_calls"), list):
            return [call for item in value["tool_calls"] if (call := self._normalize_tool(item))]
        if "tool" in value or "name" in value:
            call = self._normalize_tool(value)
            return [call] if call else []
        return []

    def _normalize_tool(self, value: Any) -> dict | None:
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

    def _parse_json_payload(self, text: str) -> Any:
        candidates = [text.strip()]
        candidates.extend(re.findall(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE))
        for candidate in candidates:
            parsed = self._loads(candidate)
            if parsed is not None:
                return parsed
        return None

    def _parse_xml_payload(self, text: str) -> ET.Element | None:
        match = re.search(r"(<response>.*?</response>)", text, flags=re.DOTALL | re.IGNORECASE)
        payload = match.group(1) if match else text.strip()
        if not payload.startswith("<"):
            return None
        try:
            return ET.fromstring(payload)
        except ET.ParseError:
            return None

    def _loads(self, payload: str) -> Any:
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(payload)
        except (SyntaxError, ValueError):
            return None

    def _dedupe(self, calls: list[dict]) -> list[dict]:
        result: list[dict] = []
        seen: set[str] = set()
        for call in calls:
            marker = json.dumps(call, sort_keys=True, ensure_ascii=False)
            if marker in seen:
                continue
            seen.add(marker)
            result.append(call)
        return result
