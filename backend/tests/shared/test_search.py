"""Tests for the shared keyword search helpers."""
from __future__ import annotations

import pytest
from sqlalchemy import column, select, table
from sqlalchemy.dialects import postgresql

from app.shared.search import MAX_KEYWORD_TERMS, build_keyword_filter, split_keyword_terms

EXPECTED = ["Java", "Backend", "Engineer", "Mandarin", "Speaking"]


@pytest.mark.parametrize(
    "keyword",
    [
        "Java Backend Engineer - Mandarin Speaking",
        "Java Backend Engineer – Mandarin Speaking",  # en dash
        "Java Backend Engineer — Mandarin Speaking",  # em dash
        "Java Backend Engineer - Mandarin Speaking",  # NBSP
        "  Java Backend Engineer - Mandarin Speaking  ",
        "Java Backend Engineer  -  Mandarin Speaking",
        "Java Backend Engineer\t-\nMandarin Speaking",
    ],
)
def test_lookalike_inputs_produce_same_terms(keyword: str) -> None:
    assert split_keyword_terms(keyword) == EXPECTED


@pytest.mark.parametrize("keyword", [None, "", "   ", " - – ", "/|,"])
def test_empty_or_separator_only_keyword_has_no_terms(keyword: str | None) -> None:
    assert split_keyword_terms(keyword) == []
    assert build_keyword_filter(keyword, [column("title")]) is None


def test_tech_terms_keep_meaningful_punctuation() -> None:
    assert split_keyword_terms("C# .NET Node.js C++") == ["C#", ".NET", "Node.js", "C++"]


def test_list_punctuation_and_ampersand_split() -> None:
    assert split_keyword_terms("Java/Kotlin, (Senior) R&D") == ["Java", "Kotlin", "Senior", "R", "D"]


def test_hyphenated_words_split_into_terms() -> None:
    assert split_keyword_terms("Full-Stack") == ["Full", "Stack"]


def test_terms_deduplicated_case_insensitively() -> None:
    assert split_keyword_terms("java Java JAVA backend") == ["java", "backend"]


def test_stop_words_dropped() -> None:
    assert split_keyword_terms("Sales and Marketing Manager") == ["Sales", "Marketing", "Manager"]
    assert split_keyword_terms("Head of the Engineering Team") == ["Head", "Engineering", "Team"]


def test_stop_words_kept_when_nothing_else_remains() -> None:
    assert split_keyword_terms("The") == ["The"]
    assert split_keyword_terms("of the") == ["of", "the"]


def test_terms_capped() -> None:
    keyword = " ".join(f"term{i}" for i in range(MAX_KEYWORD_TERMS + 5))
    assert len(split_keyword_terms(keyword)) == MAX_KEYWORD_TERMS


def _compile(keyword: str) -> tuple[str, dict]:
    jobs = table("jobs", column("title"), column("company"))
    stmt = select(jobs.c.title).where(build_keyword_filter(keyword, [jobs.c.title, jobs.c.company]))
    compiled = stmt.compile(dialect=postgresql.dialect())
    return str(compiled), compiled.params


def test_filter_requires_every_term_in_any_column() -> None:
    sql, params = _compile("Java Mandarin")
    assert sql.count(" AND ") == 1
    assert sql.count(" OR ") == 2
    assert sql.count("ILIKE") == 4
    assert sorted(set(params.values())) == ["%Java%", "%Mandarin%"]


def test_like_wildcards_in_terms_are_escaped() -> None:
    sql, params = _compile("100% snake_case")
    assert "ESCAPE '/'" in sql
    assert set(params.values()) == {"%100/%%", "%snake/_case%"}
