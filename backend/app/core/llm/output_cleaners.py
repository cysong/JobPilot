"""Helpers for lightweight cleanup of model outputs before JSON validation."""
from __future__ import annotations

from dataclasses import dataclass
import re

_FENCED_BLOCK_RE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)
_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass(frozen=True)
class JsonCandidate:
    """A cleaned JSON candidate with the transformation source recorded."""

    source: str
    text: str


def build_json_candidates(text: str) -> list[JsonCandidate]:
    """Return a small set of cleaned JSON candidates derived from raw model text."""
    cleaned = text.strip()
    candidates: list[JsonCandidate] = []

    _append_candidate(candidates, "original", cleaned)

    unfenced = strip_fenced_block(cleaned)
    if unfenced != cleaned:
        _append_candidate(candidates, "unfenced", unfenced)

    fenced_match = _JSON_BLOCK_RE.search(cleaned)
    if fenced_match:
        _append_candidate(candidates, "embedded_fenced", fenced_match.group(1).strip())

    _append_candidate(candidates, "balanced_json", extract_balanced_json(cleaned))
    if unfenced != cleaned:
        _append_candidate(
            candidates,
            "balanced_json_from_unfenced",
            extract_balanced_json(unfenced),
        )

    return candidates


def strip_fenced_block(text: str) -> str:
    """Remove a wrapping Markdown code fence when the whole payload is fenced."""
    match = _FENCED_BLOCK_RE.match(text)
    if not match:
        return text
    return match.group(1).strip()


def extract_balanced_json(text: str) -> str | None:
    """Extract the first complete top-level JSON object/array from the text."""
    start = next((idx for idx, ch in enumerate(text) if ch in "{["), -1)
    if start < 0:
        return None

    stack: list[str] = []
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack or ch != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return text[start:idx + 1].strip()
    return None


def _append_candidate(
    candidates: list[JsonCandidate],
    source: str,
    candidate: str | None,
) -> None:
    if not candidate:
        return
    item = JsonCandidate(source=source, text=candidate)
    if item not in candidates:
        candidates.append(item)
