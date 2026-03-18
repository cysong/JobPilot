"""Shared utility helpers."""
from __future__ import annotations

import uuid
from typing import Any


def generate_id(prefix: str) -> str:
    """Generate a prefixed identifier."""
    return f"{prefix}_{uuid.uuid4().hex}"


def sanitize_text_for_storage(value: str) -> str:
    """Remove control characters that commonly break DB/storage layers.

    Preserves normal whitespace controls (`\\n`, `\\r`, `\\t`) while stripping
    null bytes and other low ASCII control characters that PostgreSQL text/JSON
    columns cannot safely store.
    """
    if not value:
        return value

    sanitized_chars: list[str] = []
    for char in value:
        codepoint = ord(char)
        if char in ("\n", "\r", "\t"):
            sanitized_chars.append(char)
            continue
        if 0 <= codepoint < 32:
            continue
        sanitized_chars.append(char)
    return "".join(sanitized_chars)


def sanitize_nested_text_for_storage(value: Any) -> Any:
    """Recursively sanitize text values inside nested Python structures.

    Intended for data that may be persisted to database text or JSON columns.
    Non-container, non-string values are returned unchanged.
    """
    if isinstance(value, str):
        return sanitize_text_for_storage(value)
    if isinstance(value, list):
        return [sanitize_nested_text_for_storage(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_nested_text_for_storage(item) for item in value)
    if isinstance(value, dict):
        return {
            key: sanitize_nested_text_for_storage(item)
            for key, item in value.items()
        }
    return value
