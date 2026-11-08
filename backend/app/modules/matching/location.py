"""Location hard filter for matching v3 (docs/job_matching_v3_design.md §5.2).

Resolves a job's location against the user's preferred cities. A job is only
rejected when its city is positively known and is not one the user accepts;
anything vaguer (region only, country only, missing) is "unknown" and passes.
Pure functions, no I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Literal

import yaml

from app.modules.matching.families.normalize import strip_accents

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "nz_locations.yaml"

LocationStatus = Literal["not_applicable", "remote", "matched", "unknown", "rejected"]

_PART_SPLIT = re.compile(r",|/|&|\bor\b|\band\b")
_REMOTE_FIELD = re.compile(r"\bremote\b|\bwork from home\b|\bwfh\b")
# In titles, "remote" only counts as a qualifier: "(Remote)", "- Remote", "Remote -",
# "| Remote", trailing "Remote". "Remote Monitoring Engineer" is a role, not a location.
_REMOTE_TITLE = re.compile(
    r"\(\s*(?:fully\s+)?remote\b[^)]*\)"
    r"|(?:^|[-|,]\s*)(?:fully\s+)?remote\s*(?:[-|,]|$)"
)


@dataclass(frozen=True)
class LocationCheck:
    status: LocationStatus
    job_cities: frozenset[str] = field(default_factory=frozenset)
    job_regions: frozenset[str] = field(default_factory=frozenset)
    detail: str = ""


class NzLocations:
    """Alias tables built from config/nz_locations.yaml."""

    def __init__(self, data: dict):
        self.version = str(data.get("version") or "")
        self.city_region: dict[str, str] = {}
        self.alias_to_city: dict[str, str] = {}
        for city, spec in (data.get("cities") or {}).items():
            self.city_region[city] = spec["region"]
            for alias in [city, *(spec.get("aliases") or [])]:
                self.alias_to_city[_norm(alias)] = city
        self.alias_to_region: dict[str, str] = {}
        for region, aliases in (data.get("regions") or {}).items():
            for alias in [region, *(aliases or [])]:
                self.alias_to_region[_norm(alias)] = region
        self.non_place = {_norm(v) for v in data.get("non_place_values") or []}

    @classmethod
    def from_file(cls, path: Path) -> "NzLocations":
        with path.open("r", encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh) or {})


@lru_cache(maxsize=1)
def get_locations() -> NzLocations:
    return NzLocations.from_file(DEFAULT_CONFIG_PATH)


def _norm(value: str) -> str:
    text = strip_accents(value).lower().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip(" .-")


def _parts(value: str | None) -> list[str]:
    if not value:
        return []
    return [p for p in (_norm(x) for x in _PART_SPLIT.split(_norm(value))) if p]


def is_remote(*, title: str | None, location_label: str | None, work_types_label: str | None) -> bool:
    for field_value in (location_label, work_types_label):
        if field_value and _REMOTE_FIELD.search(_norm(field_value)):
            return True
    return bool(title and _REMOTE_TITLE.search(_norm(title)))


def check_location(
    *,
    user_locations: Iterable[str],
    location_city: str | None,
    location_label: str | None,
    work_types_label: str | None = None,
    title: str | None = None,
    locations: NzLocations | None = None,
) -> LocationCheck:
    """Decide whether a job passes the user's location preference."""
    preferred = {c for c in user_locations if c}
    if not preferred:
        return LocationCheck("not_applicable")
    if is_remote(title=title, location_label=location_label, work_types_label=work_types_label):
        return LocationCheck("remote", detail="remote")

    loc = locations or get_locations()
    cities: set[str] = set()
    regions: set[str] = set()
    for part in [*_parts(location_city), *_parts(location_label)]:
        if part in loc.non_place:
            continue
        if part in loc.alias_to_city:
            cities.add(loc.alias_to_city[part])
        if part in loc.alias_to_region:
            regions.add(loc.alias_to_region[part])

    if cities & preferred:
        return LocationCheck("matched", frozenset(cities), frozenset(regions))

    if cities:
        # A preference city was identified, but not one the user accepts.
        return LocationCheck(
            "rejected", frozenset(cities), frozenset(regions), detail=", ".join(sorted(cities))
        )

    city_field = _norm(location_city) if location_city else ""
    if (
        city_field
        and city_field not in loc.non_place
        and city_field not in loc.alias_to_region
        and not _PART_SPLIT.search(city_field)
    ):
        # A specific locality outside every preference city (e.g. "Taupo", "Invercargill").
        return LocationCheck("rejected", frozenset(), frozenset(regions), detail=location_city or "")

    return LocationCheck("unknown", frozenset(), frozenset(regions), detail=location_label or "")
