"""Semantic validation for OCR text independent of provider transport."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)", re.IGNORECASE)
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)", re.IGNORECASE)
_HTML_IMAGE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_IMAGE_PATH = re.compile(r"(?:^|\s)(?:[\w./\\-]+\.(?:png|jpe?g|webp|bmp|tiff?))(?:\s|$)", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"<\|[^|>]+\|>|\[(?:image|img|placeholder|unreadable)\]|\{\{[^}]+\}\}", re.IGNORECASE)
_DETECTION_PLACEHOLDER = re.compile(r"<\|det\|>\s*(?:image|img|figure)\s*\[[^\]]*\]\s*<\|/det\|>", re.IGNORECASE)
_DETECTION_TAG = re.compile(r"<\|/?det\|>(?:[^\n<]*?\[[^\]]*\])?", re.IGNORECASE)


@dataclass(frozen=True)
class RecognitionValidation:
    valid: bool
    reason: str
    visible_text_length: int
    markdown_image_count: int

    def metadata(self) -> dict[str, object]:
        return {"recognition_valid": self.valid, "recognition_validation_reason": self.reason, "visible_text_length": self.visible_text_length, "markdown_image_count": self.markdown_image_count}


def validate_recognition(text: str | None) -> RecognitionValidation:
    raw = str(text or "")
    markdown_images = len(_MARKDOWN_IMAGE.findall(raw))
    visible = _DETECTION_PLACEHOLDER.sub(" ", raw)
    visible = _DETECTION_TAG.sub(" ", visible)
    visible = _MARKDOWN_IMAGE.sub(" ", visible)
    visible = _HTML_IMAGE.sub(" ", visible)
    visible = _MARKDOWN_LINK.sub(lambda match: match.group(1), visible)
    visible = _PLACEHOLDER.sub(" ", visible)
    visible = re.sub(r"\[\s*\d+(?:\s*,\s*\d+){3}\s*\]", " ", visible)
    visible = _IMAGE_PATH.sub(" ", visible)
    visible = re.sub(r"[`*_#>|~-]+", " ", visible)
    visible = " ".join(visible.split())
    visible_length = len(re.sub(r"\s+", "", visible))
    if not raw.strip():
        reason = "empty_or_whitespace"
    elif visible_length == 0 and markdown_images:
        reason = "markdown_images_only"
    elif visible_length == 0:
        reason = "no_visible_text"
    else:
        reason = "visible_text_present"
    return RecognitionValidation(visible_length > 0, reason, visible_length, markdown_images)
