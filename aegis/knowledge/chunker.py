"""Deterministic text chunking for local knowledge documents."""

from __future__ import annotations


def chunk_text(text: str, *, max_chars: int = 1200) -> list[str]:
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            _flush(chunks, current)
            current_size = 0
            chunks.extend(_split_long(paragraph, max_chars=max_chars))
            continue
        projected = current_size + len(paragraph) + (2 if current else 0)
        if current and projected > max_chars:
            _flush(chunks, current)
            current_size = 0
        current.append(paragraph)
        current_size += len(paragraph) + (2 if len(current) > 1 else 0)

    _flush(chunks, current)
    return chunks


def _flush(chunks: list[str], current: list[str]) -> None:
    if current:
        chunks.append("\n\n".join(current).strip())
        current.clear()


def _split_long(text: str, *, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for word in words:
        if current and current_size + len(word) + 1 > max_chars:
            chunks.append(" ".join(current))
            current = []
            current_size = 0
        current.append(word)
        current_size += len(word) + (1 if current_size else 0)
    if current:
        chunks.append(" ".join(current))
    return chunks
