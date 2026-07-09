"""Parsers for local knowledge documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .chunker import chunk_text


def parse_document(path: Path, text: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_json(text, fallback_title=path.stem)
    if suffix == ".md" or _is_markdown_like(path):
        return parse_markdown(text, fallback_title=path.stem)
    return parse_text(text, fallback_title=path.stem)


def parse_markdown(text: str, *, fallback_title: str = "") -> dict[str, Any]:
    headings = _headings(text)
    title = headings[0]["title"] if headings else fallback_title
    sections = _markdown_sections(text)
    chunks: list[dict[str, Any]] = []
    for section_index, section in enumerate(sections):
        for chunk in chunk_text(section["text"]):
            chunks.append(
                {
                    "text": chunk,
                    "metadata": {
                        "section": section["title"],
                        "section_index": section_index,
                    },
                }
            )
    return {
        "title": title,
        "type": "markdown",
        "text": text,
        "chunks": chunks,
        "metadata": {"headings": headings},
    }


def parse_text(text: str, *, fallback_title: str = "") -> dict[str, Any]:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    title = first_line[:80] if first_line else fallback_title
    return {
        "title": title,
        "type": "text",
        "text": text,
        "chunks": [{"text": chunk, "metadata": {}} for chunk in chunk_text(text)],
        "metadata": {},
    }


def parse_json(text: str, *, fallback_title: str = "") -> dict[str, Any]:
    try:
        data = json.loads(text)
        pretty = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        title = _json_title(data) or fallback_title
    except json.JSONDecodeError:
        pretty = text
        title = fallback_title
    return {
        "title": title,
        "type": "json",
        "text": pretty,
        "chunks": [{"text": chunk, "metadata": {}} for chunk in chunk_text(pretty)],
        "metadata": {},
    }


def _is_markdown_like(path: Path) -> bool:
    name = path.name.upper()
    return name.startswith("README") or name.startswith("RFC")


def _headings(text: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append(
                {
                    "level": len(match.group(1)),
                    "title": match.group(2).strip(),
                    "line": line_number,
                }
            )
    return headings


def _markdown_sections(text: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match and current_lines:
            sections.append(
                {"title": current_title, "text": "\n".join(current_lines).strip()}
            )
            current_lines = []
        if match:
            current_title = match.group(2).strip()
        current_lines.append(line)
    if current_lines:
        sections.append({"title": current_title, "text": "\n".join(current_lines).strip()})
    return sections or [{"title": "", "text": text}]


def _json_title(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("title", "name", "id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""
