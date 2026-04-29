"""Regression guard: ``list_my_matches`` must not return to N+1.

Earlier the route ran ``JobRepository.get_by_id`` and
``ResumeRepository.get_by_id`` once per match inside the result-building
loop. It was rewritten to batch-load via ``get_brief_map`` /
``get_by_ids_map`` outside the loop. This test parses the route's
source AST and fails if any of the per-row DB lookups reappear inside
a ``for`` loop body — much lighter than spinning up a DB / Pydantic
roundtrip just to count queries, while still catching the exact
regression we care about.

If you legitimately need to fetch something per-match, prefer adding a
new batch repository helper instead of reverting to a per-row lookup.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from app.modules.jobs.router import list_my_matches


# (owner_class_name, method_name) pairs that must never appear inside a
# loop in list_my_matches. Keep this conservative — only methods that
# fetch a single row from the DB.
_FORBIDDEN_PER_ROW_LOOKUPS: frozenset[tuple[str, str]] = frozenset(
    {
        ("JobRepository", "get_by_id"),
        ("JobRepository", "get_brief"),
        ("JobRepository", "get_content"),
        ("ResumeRepository", "get_by_id"),
        ("ResumeRepository", "get_with_document"),
    }
)


def _function_ast(fn) -> ast.AST:
    src = textwrap.dedent(inspect.getsource(fn))
    return ast.parse(src).body[0]


def _calls_inside_loops(fn_node: ast.AST):
    """Yield every ``ast.Call`` whose parent chain crosses a for/async-for."""
    for child in ast.walk(fn_node):
        if isinstance(child, (ast.For, ast.AsyncFor)):
            for inner in ast.walk(child):
                if isinstance(inner, ast.Call):
                    yield inner


def test_list_my_matches_has_no_per_row_db_lookup_in_loop():
    fn_node = _function_ast(list_my_matches)
    offenders: list[str] = []
    for call in _calls_inside_loops(fn_node):
        # Match ``Owner.method(...)`` style attribute calls.
        func = call.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            owner = func.value.id
            method = func.attr
            if (owner, method) in _FORBIDDEN_PER_ROW_LOOKUPS:
                offenders.append(f"{owner}.{method}")

    assert not offenders, (
        "list_my_matches contains forbidden per-row DB lookups inside a "
        f"loop: {sorted(set(offenders))}. Use the batch variants "
        "(JobRepository.get_brief_map / ResumeRepository.get_by_ids_map) "
        "outside the loop, or add a new batch helper."
    )
