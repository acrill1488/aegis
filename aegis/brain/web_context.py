"""
Web context module for AEGIS brain.
Provides functionality to determine if a prompt needs web context
and to build web context from prompts.
"""

import re


WEB_KEYWORDS = [
    "актуаль",
    "сейчас",
    "сегодня",
    "последн",
    "новост",
    "цен",
    "стоимост",
    "стоит",
    "курс",
    "погод",
    "документац",
    "релиз",
    "github",
    "huggingface",
    "hugging face",
    "url",
    "ссылк",
    "сайт",
    "интернет",
    "2025",
    "2026",
    "новая модель",
    "последняя модель",
    "актуальная модель",
    "библиотек",
    "сравн",
    "найд",
    "нов верси",
]


def needs_web_context(prompt: str) -> bool:
    """
    Determine if a prompt requires web context.

    Args:
        prompt (str): The user's prompt

    Returns:
        bool: True if the prompt contains web context keywords, False otherwise
    """

    text = prompt.lower()
    return any(keyword in text for keyword in WEB_KEYWORDS)


def build_web_context(core, prompt: str) -> str:
    """
    Build web context from a prompt.

    Args:
        core: The Aegis core instance
        prompt (str): The user's prompt

    Returns:
        str: Web context or empty string
    """

    url_pattern = r"https?://[^\s]+"
    urls = re.findall(url_pattern, prompt)

    if urls:
        return f"URL: {urls[0]}\nFailed to fetch content\n"

    return ""
