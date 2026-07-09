"""Stub VLM provider."""

from __future__ import annotations


class StubVLMProvider:
    name = "stub"

    def available(self) -> bool:
        return True

    def describe(self, image_path: str, prompt: str | None = None) -> dict:
        return {
            "provider": self.name,
            "image_path": image_path,
            "description": "Vision-language provider is not configured in v1.",
            "prompt": prompt,
            "metadata": {"stub": True},
        }

    def locate(self, image_path: str, query: str) -> dict:
        return {
            "provider": self.name,
            "image_path": image_path,
            "query": query,
            "regions": [],
            "metadata": {"stub": True},
        }

    def reason(self, image_path: str, question: str) -> dict:
        return {
            "provider": self.name,
            "image_path": image_path,
            "question": question,
            "answer": "Vision-language reasoning is not configured in v1.",
            "metadata": {"stub": True},
        }
