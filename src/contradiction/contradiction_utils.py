"""
Utility functions for contradiction detection.
"""

from typing import Any


def normalize_text(text: Any) -> str:
    """
    Convert text into a clean single-spaced string.
    """

    if text is None:
        return ""

    return " ".join(str(text).split())


def get_article_field(article: Any, field_name: str, default: str = "") -> str:
    """
    Read a field from either an article dictionary or an article object.
    """

    if article is None:
        return default

    if isinstance(article, dict):
        value = article.get(field_name, default)
    else:
        value = getattr(article, field_name, default)

    return normalize_text(value)


def combine_article(article: Any) -> str:
    """
    Combine the useful textual fields of an article for NLI comparison.

    Supports both dictionaries and model objects.
    """

    title = get_article_field(article, "title")

    description = (
        get_article_field(article, "description")
        or get_article_field(article, "summary")
    )

    content = (
        get_article_field(article, "content")
        or get_article_field(article, "text")
    )

    article_parts = [
        part
        for part in (title, description, content)
        if part
    ]

    return "\n".join(article_parts)