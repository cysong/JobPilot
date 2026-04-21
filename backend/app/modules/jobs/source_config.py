"""
Source display metadata loader.

Reads backend/config/sources.yaml at first access and memoizes the result
for the lifetime of the process. Invalid or missing files fall back to an
empty list so the API stays stable even in degraded environments.

To refresh without a restart, call `reload_source_metas()`.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.modules.jobs.schemas import SourceMeta

logger = logging.getLogger(__name__)

# backend/app/modules/jobs/source_config.py  ->  backend/
_BACKEND_DIR = Path(__file__).resolve().parents[3]
_CONFIG_PATH = _BACKEND_DIR / "config" / "sources.yaml"


def _coerce_entry(raw: Any) -> SourceMeta | None:
    """Validate a single yaml entry; swallow-and-log individual failures."""
    if not isinstance(raw, dict):
        logger.warning("sources.yaml entry is not a mapping: %r", raw)
        return None
    try:
        return SourceMeta.model_validate(raw)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Invalid source entry %r: %s", raw, exc)
        return None


@lru_cache(maxsize=1)
def load_source_metas() -> list[SourceMeta]:
    """Load enabled source metadata from YAML. Memoized per-process."""
    if not _CONFIG_PATH.exists():
        logger.warning("sources.yaml not found at %s", _CONFIG_PATH)
        return []

    try:
        payload = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse sources.yaml: %s", exc)
        return []

    raw_items = payload.get("sources") or []
    if not isinstance(raw_items, list):
        logger.warning("sources.yaml top-level `sources` is not a list")
        return []

    metas: list[SourceMeta] = []
    for raw in raw_items:
        meta = _coerce_entry(raw)
        if meta is not None and meta.enabled:
            metas.append(meta)
    return metas


def reload_source_metas() -> list[SourceMeta]:
    """Clear the cache and reload. Useful for tests and admin reload hooks."""
    load_source_metas.cache_clear()
    return load_source_metas()
