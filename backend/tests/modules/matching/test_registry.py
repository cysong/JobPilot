"""Tests for the role family registry and the shipped role_families.yaml."""
from __future__ import annotations

import pytest

from app.modules.matching.families.registry import RoleFamilyRegistry, get_registry


def _registry(**families) -> RoleFamilyRegistry:
    return RoleFamilyRegistry.from_dict({"version": "t1", "families": families})


def test_adjacency_is_symmetric():
    reg = _registry(a={"adjacent": ["b"]}, b={}, c={})
    assert reg.adjacent("a") == {"b"}
    assert reg.adjacent("b") == {"a"}
    assert reg.adjacent("c") == frozenset()


def test_relation():
    reg = _registry(a={"adjacent": ["b"]}, b={}, c={})
    assert reg.relation("a", "a") == "same"
    assert reg.relation("a", "b") == "adjacent"
    assert reg.relation("b", "a") == "adjacent"
    assert reg.relation("a", "c") is None


def test_rejects_unknown_adjacent_family():
    with pytest.raises(ValueError, match="unknown adjacent"):
        _registry(a={"adjacent": ["missing"]})


def test_rejects_self_adjacency():
    with pytest.raises(ValueError, match="itself"):
        _registry(a={"adjacent": ["a"]})


def test_requires_version_and_families():
    with pytest.raises(ValueError, match="version"):
        RoleFamilyRegistry.from_dict({"families": {"a": {}}})
    with pytest.raises(ValueError, match="no families"):
        RoleFamilyRegistry.from_dict({"version": "x", "families": {}})


def test_shipped_config_loads_and_covers_design_families():
    reg = get_registry()
    assert reg.version == "f2"
    expected = {
        "software_dev", "qa_test", "devops_platform", "infrastructure", "it_support",
        "data_engineering", "data_analytics", "ml_ai", "architecture", "integration",
        "security", "business_analysis", "product_delivery", "eng_management",
        "ai_data_work", "research", "other_engineering", "other", "app_support",
    }
    assert set(reg.keys) == expected


def test_shipped_config_adjacency_matches_design():
    reg = get_registry()
    assert reg.adjacent("qa_test") == {"software_dev", "devops_platform"}
    assert reg.adjacent("app_support") == {"software_dev", "it_support"}
    assert "app_support" in reg.adjacent("software_dev")
    assert "devops_platform" in reg.adjacent("software_dev")
    # Non-IT and gig families are isolated so they never reach the LLM via adjacency.
    for isolated in ("ai_data_work", "research", "other_engineering", "other"):
        assert reg.adjacent(isolated) == frozenset()


def test_every_family_has_description_and_examples_for_the_classifier():
    reg = get_registry()
    for key in reg.keys:
        fam = reg.get(key)
        assert fam.description, key
        assert fam.examples, key
    catalog = reg.catalog_for_prompt()
    assert catalog.count("\n") == len(reg.keys) - 1
    assert "- software_dev:" in catalog
