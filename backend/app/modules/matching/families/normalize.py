"""Job title normalization into the cache key used for role family lookup.

See docs/job_matching_v3_design.md §4.2. Pure functions, no I/O.
"""
from __future__ import annotations

import re
import unicodedata

TITLE_KEY_MAX_LENGTH = 500

# Seniority words removed wherever they appear as a standalone token.
_SENIORITY_ANYWHERE = {
    "senior", "snr", "sr", "junior", "jnr", "jr", "intermediate", "mid-level",
    "midlevel", "graduate", "grad", "intern", "internship",
}
# Seniority words removed only as a leading modifier: "lead developer" -> "developer",
# but "tech lead" / "team lead" keep their meaning.
_SENIORITY_LEADING_ONLY = {"lead", "principal", "staff", "associate"}

# Employment-type phrases, longest first so "fixed term" wins over "term".
_EMPLOYMENT_PHRASES = (
    "fixed term", "fixed-term", "part time", "part-time", "full time", "full-time",
    "entry level", "entry-level", "maternity cover", "parental leave cover",
    "contractor", "contract", "temporary", "temp", "permanent", "casual", "ftc",
)
_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
# Contract durations and dates: "12 month", "6-month", "November 2026", "2027".
_DURATION_OR_DATE = re.compile(
    rf"\b\d+\s*-?\s*months?\b|\b(?:{_MONTHS})\s+\d{{4}}\b|\b(?:19|20)\d{{2}}\b"
)
# Trailing level markers: "software engineer ii", "engineer level 3", "developer l2".
_LEVEL_SUFFIX = re.compile(r"(?:\s+(?:level\s*\d+|l\d|i{1,3}|iv|\d+))+$")

_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}")
_DASHES = re.compile(r"[‐-―−]")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_EDGE_PUNCT = " -|,/:;.&"


def strip_accents(text: str) -> str:
    """Remove diacritics (Māori macrons, accents) for comparison."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_title(title: str | None) -> str:
    """Return the cache key for a job title.

    Lowercases, unifies punctuation, drops bracketed qualifiers, seniority and
    employment-type modifiers. Text after " - " or " | " is kept on purpose
    (e.g. "Technical Lead - Data Platform"). Never returns an empty key for a
    non-empty title: if stripping would remove everything, the less-stripped
    form is kept.
    """
    if not title:
        return ""

    text = strip_accents(title).translate(_QUOTES).lower()
    text = _DASHES.sub("-", text)
    text = _BRACKETS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(_EDGE_PUNCT)
    base = text

    text = _DURATION_OR_DATE.sub(" ", text)
    for phrase in _EMPLOYMENT_PHRASES:
        text = re.sub(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", " ", text)
    text = _collapse(text)

    tokens = text.split(" ")
    # Abbreviations may carry a trailing period ("Sr. Developer").
    tokens = [t for t in tokens if not _is_seniority_token(t)]
    while len(tokens) > 1 and tokens[0].rstrip(".") in _SENIORITY_LEADING_ONLY:
        tokens = tokens[1:]
    text = _collapse(" ".join(tokens))
    text = _collapse(_LEVEL_SUFFIX.sub("", text))

    if not text:
        text = base
    return text[:TITLE_KEY_MAX_LENGTH]


def _is_seniority_token(token: str) -> bool:
    """True for "senior", "sr.", and slash-joined forms like "intermediate/senior"."""
    parts = [p.rstrip(".") for p in token.split("/")]
    return all(p in _SENIORITY_ANYWHERE for p in parts)


def _collapse(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    # Remove separators left dangling by removed words, e.g. "engineer - " or "/ developer".
    text = re.sub(r"\s*([-|/,])\s*(?=[-|/,]|$)", "", text)
    text = re.sub(r"^\s*[-|/,]\s*", "", text)
    return text.strip(_EDGE_PUNCT).strip()
