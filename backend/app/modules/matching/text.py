"""Text helpers shared by the v3 classifier, judge and validator. Pure functions."""
from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser

from app.modules.matching.families.normalize import strip_accents

_BLOCK_TAGS = {
    "p", "div", "br", "ul", "ol", "table", "tr", "section", "article", "header", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS or tag == "li":
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    """Convert job description HTML to plain text, keeping list items as "- " lines."""
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line in ("", "-"):
            if out and out[-1] != "":
                out.append("")
            continue
        out.append(line)
    return "\n".join(out).strip()


_QUOTE_CHARS = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
})
_BULLET_PREFIX = re.compile(r"(?m)^\s*(?:[-*•●▪]|\d+[.)])\s+")
_MARKDOWN_EMPHASIS = re.compile(r"[*_`]+")


def normalize_for_quote(text: str | None) -> str:
    """Normalize text so verbatim quotes survive HTML/Markdown formatting differences.

    Both sides of a quote check go through this: decode punctuation variants,
    drop list markers and Markdown emphasis, fold accents, collapse whitespace,
    lowercase.
    """
    if not text:
        return ""
    value = text.translate(_QUOTE_CHARS)
    value = _BULLET_PREFIX.sub("", value)
    value = _MARKDOWN_EMPHASIS.sub("", value)
    value = strip_accents(value).lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .;:,")


def quote_in(quote: str | None, *sources: str | None) -> bool:
    """True when ``quote`` appears verbatim (after normalization) in any source."""
    needle = normalize_for_quote(quote)
    if not needle:
        return False
    return any(needle in normalize_for_quote(src) for src in sources if src)


def sha256_hex(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
