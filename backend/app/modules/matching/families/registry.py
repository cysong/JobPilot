"""Role family registry loaded from config/role_families.yaml.

Pure lookups (no DB, no LLM). Adjacency is made symmetric on load.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "role_families.yaml"

FamilyRelation = Literal["same", "adjacent"]


@dataclass(frozen=True)
class RoleFamily:
    key: str
    label: str
    label_zh: str
    description: str
    examples: tuple[str, ...]


class RoleFamilyRegistry:
    """In-memory view of the role family configuration."""

    def __init__(self, version: str, families: dict[str, RoleFamily], adjacency: dict[str, frozenset[str]]):
        self.version = version
        self._families = families
        self._adjacency = adjacency

    @classmethod
    def from_dict(cls, data: dict) -> "RoleFamilyRegistry":
        version = str(data.get("version") or "").strip()
        if not version:
            raise ValueError("role_families config is missing 'version'")
        raw_families = data.get("families") or {}
        if not raw_families:
            raise ValueError("role_families config has no families")

        families: dict[str, RoleFamily] = {}
        edges: dict[str, set[str]] = {key: set() for key in raw_families}
        for key, spec in raw_families.items():
            spec = spec or {}
            families[key] = RoleFamily(
                key=key,
                label=spec.get("label") or key,
                label_zh=spec.get("label_zh") or spec.get("label") or key,
                description=spec.get("description") or "",
                examples=tuple(spec.get("examples") or ()),
            )
            for other in spec.get("adjacent") or ():
                if other not in raw_families:
                    raise ValueError(f"Family '{key}' lists unknown adjacent family '{other}'")
                if other == key:
                    raise ValueError(f"Family '{key}' cannot be adjacent to itself")
                edges[key].add(other)
                edges[other].add(key)

        adjacency = {key: frozenset(values) for key, values in edges.items()}
        return cls(version, families, adjacency)

    @classmethod
    def from_file(cls, path: Path) -> "RoleFamilyRegistry":
        with path.open("r", encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh) or {})

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._families)

    def get(self, key: str) -> RoleFamily | None:
        return self._families.get(key)

    def is_valid(self, key: str | None) -> bool:
        return key is not None and key in self._families

    def adjacent(self, key: str) -> frozenset[str]:
        return self._adjacency.get(key, frozenset())

    def relation(self, job_family: str, resume_family: str) -> FamilyRelation | None:
        """How a resume's family relates to a job's family; None when unrelated."""
        if job_family == resume_family:
            return "same"
        if resume_family in self.adjacent(job_family):
            return "adjacent"
        return None

    def catalog_for_prompt(self) -> str:
        """Render families as a compact list for classifier prompts."""
        lines = []
        for fam in self._families.values():
            examples = ", ".join(fam.examples[:8])
            lines.append(f"- {fam.key}: {fam.description} Examples: {examples}")
        return "\n".join(lines)


@lru_cache(maxsize=1)
def get_registry() -> RoleFamilyRegistry:
    """Process-wide registry loaded from the default config file."""
    return RoleFamilyRegistry.from_file(DEFAULT_CONFIG_PATH)
