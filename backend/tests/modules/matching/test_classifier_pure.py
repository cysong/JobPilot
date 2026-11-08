"""Tests for title classification prompt building and output parsing."""
from __future__ import annotations

import json

import pytest

from agent_configs.schemas import JobFamilyReading, TitleClassificationBatch
from app.modules.matching.families.classifier import (
    TitleToClassify,
    build_jd_read_input,
    build_title_batch_input,
    parse_jd_read,
    parse_title_batch,
)
from app.modules.matching.families.registry import get_registry

REG = get_registry()


def test_batch_input_contains_catalog_and_titles():
    payload = json.loads(build_title_batch_input(REG, [TitleToClassify("software engineer", "Senior Software Engineer")]))
    assert "- software_dev:" in payload["families"]
    assert payload["titles"] == [{"title_key": "software engineer", "example_title": "Senior Software Engineer"}]


def test_parse_maps_valid_ambiguous_unknown_and_skips_extras():
    output = TitleClassificationBatch.model_validate({"items": [
        {"title_key": "software engineer", "role_family": "software_dev", "ambiguous": False},
        {"title_key": "engineer", "role_family": None, "ambiguous": True},
        {"title_key": "data wizard", "role_family": "wizardry", "ambiguous": False},  # unknown family
        {"title_key": "not requested", "role_family": "other", "ambiguous": False},
        {"title_key": "software engineer", "role_family": "other", "ambiguous": False},  # duplicate ignored
        {"title_key": "qa engineer", "role_family": "qa_test", "ambiguous": True},  # ambiguous wins
    ]})
    results = {r.title_key: r for r in parse_title_batch(
        output, ["software engineer", "engineer", "data wizard", "qa engineer", "skipped by model"], REG)}
    assert results["software engineer"].status == "classified"
    assert results["software engineer"].role_family == "software_dev"
    for key in ("engineer", "data wizard", "qa engineer"):
        assert results[key].status == "ambiguous"
        assert results[key].role_family is None
    assert "not requested" not in results
    assert "skipped by model" not in results  # retried later


def test_parse_accepts_plain_dict():
    results = parse_title_batch(
        {"items": [{"title_key": "devops engineer", "role_family": "devops_platform", "ambiguous": False}]},
        ["devops engineer"], REG,
    )
    assert results[0].role_family == "devops_platform"


def test_jd_read_input_uses_text_excerpt():
    html = "<p>About us: we make cheese.</p><ul><li>Write Playwright tests</li></ul>" + "<p>x</p>" * 2000
    payload = json.loads(build_jd_read_input(REG, "Automation Engineer", html, char_limit=60))
    assert payload["title"] == "Automation Engineer"
    assert payload["description_excerpt"].startswith("About us: we make cheese.")
    assert "<" not in payload["description_excerpt"]
    assert len(payload["description_excerpt"]) <= 60


def test_jd_read_input_falls_back_to_abstract():
    payload = json.loads(build_jd_read_input(REG, "Engineer", None, abstract="PLC programming role"))
    assert payload["description_excerpt"] == "PLC programming role"


def test_parse_jd_read_rejects_unknown_family():
    assert parse_jd_read({"role_family": "qa_test", "reason": "Playwright tests"}, REG).role_family == "qa_test"
    with pytest.raises(ValueError):
        parse_jd_read(JobFamilyReading(role_family="ambiguous", reason="?"), REG)
