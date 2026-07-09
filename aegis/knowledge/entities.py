"""Heuristic entity extraction for local knowledge documents."""

from __future__ import annotations

import re
from hashlib import sha1
from typing import Any

from .models import KnowledgeEntity


CONCEPT_TERMS = {
    "Runtime",
    "Engine",
    "Skill",
    "Mission",
    "Project",
    "Recovery",
    "Reflection",
    "Planner",
}


def extract_entities(
    *,
    document_id: str,
    text: str,
    parsed_metadata: dict[str, Any] | None = None,
) -> list[KnowledgeEntity]:
    entities: dict[tuple[str, str], KnowledgeEntity] = {}

    for heading in (parsed_metadata or {}).get("headings", []):
        name = str(heading.get("title") or "").strip()
        if name:
            _add(entities, document_id, name, "heading", {"level": heading.get("level")})

    for match in re.finditer(r"`([^`\n]+)`", text):
        name = match.group(1).strip()
        if _valid_identifierish(name):
            _add(entities, document_id, name, "code", {})

    for pattern, entity_type in (
        (r"\b[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]+)+\b", "identifier"),
        (r"\b[a-z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*\b", "identifier"),
        (r"\b[a-z]+(?:_[a-z0-9]+)+\b", "identifier"),
    ):
        for match in re.finditer(pattern, text):
            _add(entities, document_id, match.group(0), entity_type, {})

    for term in CONCEPT_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", text):
            _add(entities, document_id, term, "concept", {})

    return sorted(entities.values(), key=lambda item: (item.type, item.name.lower()))


def _add(
    entities: dict[tuple[str, str], KnowledgeEntity],
    document_id: str,
    name: str,
    type: str,
    metadata: dict[str, Any],
) -> None:
    key = (type, name)
    if key in entities:
        return
    digest = sha1(f"{document_id}:{type}:{name}".encode("utf-8")).hexdigest()[:16]
    entities[key] = KnowledgeEntity(
        id=f"entity_{digest}",
        name=name,
        type=type,
        document_id=document_id,
        metadata=metadata,
    )


def _valid_identifierish(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_.:-]*$", value))
