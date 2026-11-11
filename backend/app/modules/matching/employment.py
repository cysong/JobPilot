"""Advertisers that post crowd / paid-per-task work instead of jobs (config/non_employment.yaml)."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

_CONFIG = Path(__file__).parent / "config" / "non_employment.yaml"
_SUFFIXES = re.compile(r"\b(limited|ltd|inc|llc|pty|co|corp|corporation|group|nz|new zealand)\b")


def company_key(name: str | None) -> str:
    """Lowercase, drop company suffixes and punctuation: 'Joblet-AI Ltd.' -> 'joblet ai'."""
    text = _SUFFIXES.sub(" ", (name or "").lower())
    return " ".join(re.findall(r"[a-z0-9]+", text))


@lru_cache(maxsize=1)
def _blocked_keys() -> tuple[str, ...]:
    data = yaml.safe_load(_CONFIG.read_text(encoding="utf-8")) or {}
    return tuple(k for k in (company_key(c) for c in data.get("companies") or ()) if k)


def is_non_employment_company(*names: str | None) -> bool:
    """True when any of the job's company names (advertiser, company) is on the list."""
    for name in names:
        key = company_key(name)
        if key and any(key == b or key.startswith(b + " ") for b in _blocked_keys()):
            return True
    return False


NON_EMPLOYMENT_REASON = "Crowd or paid-per-task work platform, not an employment role."
