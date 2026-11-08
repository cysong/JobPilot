"""Tests for HTML-to-text conversion and quote normalization."""
from __future__ import annotations

from app.modules.matching.text import html_to_text, normalize_for_quote, quote_in, sha256_hex

SEEK_HTML = (
    "<p><strong>About the role</strong></p>"
    "<p>We&rsquo;re looking for a&nbsp;<em>Senior Engineer</em>.</p>"
    "<ul><li>5+ years of C# &amp; .NET</li><li>Azure experience</li></ul>"
    "<script>track()</script><p>Apply now</p>"
)


def test_html_to_text_keeps_structure_and_decodes_entities():
    text = html_to_text(SEEK_HTML)
    assert text.splitlines() == [
        "About the role",
        "",
        "We’re looking for a Senior Engineer.",
        "",
        "- 5+ years of C# & .NET",
        "",
        "- Azure experience",
        "",
        "Apply now",
    ]
    assert "track()" not in text


def test_html_to_text_handles_empty_and_plain_text():
    assert html_to_text(None) == ""
    assert html_to_text("") == ""
    assert html_to_text("Plain description") == "Plain description"


def test_quote_survives_formatting_differences():
    jd = html_to_text(SEEK_HTML)
    assert quote_in("We're looking for a Senior Engineer", jd)  # straight vs curly apostrophe
    assert quote_in("5+ years of C# & .NET", jd)  # list marker stripped
    assert quote_in("azure EXPERIENCE", jd)


def test_quote_matches_markdown_resume_text():
    resume = "- Built **REST APIs** with *ASP.NET Core* — 4 years\n- Mentored 3 juniors"
    assert quote_in("Built REST APIs with ASP.NET Core - 4 years", resume)
    assert not quote_in("Built GraphQL APIs", resume)


def test_quote_checks_any_source_and_rejects_empty():
    assert quote_in("Kafka", "no", "uses Kafka daily")
    assert not quote_in("", "anything")
    assert not quote_in(None, "anything")
    assert not quote_in("x", None, "")


def test_normalize_for_quote_folds_accents_and_whitespace():
    assert normalize_for_quote("  Māori   Health.  ") == "maori health"


def test_sha256_is_stable():
    assert sha256_hex("abc") == sha256_hex("abc")
    assert len(sha256_hex(None)) == 64
