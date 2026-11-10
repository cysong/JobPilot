"""Keyword search helpers shared by list endpoints.

A raw ``ILIKE '%keyword%'`` only matches when the user's input is
byte-identical to a substring of the stored text, so titles pasted from
job boards (en/em dashes, non-breaking spaces, stray leading/trailing
spaces, doubled spaces) silently return nothing. Instead the keyword is
split into terms on whitespace and separator punctuation, and every term
must appear in at least one of the searched columns.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

# Whitespace (``\s`` covers NBSP and other Unicode spaces), ASCII hyphen,
# Unicode dashes U+2010–U+2015, minus sign, and list/grouping punctuation.
# Characters that carry meaning inside tech terms (``#``, ``+``, ``.``) are
# deliberately kept so "C#", "C++", ".NET" and "Node.js" stay intact.
_SEPARATORS = re.compile(r"[\s\-‐-―−/|,;:&()\[\]{}\"'‘’“”]+")

# Connector words dropped from multi-term searches. Under AND matching they
# only hurt: "and" fails against a title written with "&", and as a
# substring it hits "Mandarin" / "candidate" anyway, so it never narrows.
# Kept short on purpose; anything that could be a real title/company term
# (e.g. "it", "us", "go") stays out of this list.
_STOP_WORDS = frozenset(
    {"a", "an", "and", "the", "of", "for", "to", "in", "on", "at", "with", "or"}
)

# Bounds the size of the generated WHERE clause (terms x columns).
MAX_KEYWORD_TERMS = 8

# Not a backslash: the PostgreSQL dialect renders ESCAPE '\' as '\\', which
# Postgres rejects as a two-character escape string. "/" is a separator, so
# it never appears inside a term and needs no escaping of its own.
_LIKE_ESCAPE = "/"


def split_keyword_terms(keyword: str | None) -> list[str]:
    """Split a free-text keyword into de-duplicated, non-empty search terms."""
    if not keyword:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for term in _SEPARATORS.split(keyword):
        folded = term.casefold()
        if term and folded not in seen:
            seen.add(folded)
            terms.append(term)
    # Drop stop words, unless that would leave nothing to search for
    # (e.g. the user searched just "The").
    meaningful = [term for term in terms if term.casefold() not in _STOP_WORDS]
    return (meaningful or terms)[:MAX_KEYWORD_TERMS]


def _escape_like(term: str) -> str:
    return (
        term.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", _LIKE_ESCAPE + "%")
        .replace("_", _LIKE_ESCAPE + "_")
    )


def build_keyword_filter(
    keyword: str | None,
    columns: Sequence[ColumnElement],
) -> ColumnElement[bool] | None:
    """Return a filter requiring every keyword term to match one of ``columns``.

    Returns ``None`` when the keyword has no searchable terms (empty, or only
    separators), so callers can skip the filter entirely.
    """
    terms = split_keyword_terms(keyword)
    if not terms or not columns:
        return None
    return and_(
        *(
            or_(
                *(
                    column.ilike(f"%{_escape_like(term)}%", escape=_LIKE_ESCAPE)
                    for column in columns
                )
            )
            for term in terms
        )
    )
