"""Skill name normalisation and proficiency ordering.

Resume analysis is an LLM step, so the same technology arrives under several
spellings ("Pytest" / "pytest", "CSS" / "CSS3", "CI/CD" / "Continuous
Integration and Continuous Delivery"). Everything that decides whether two
skills are the same one goes through ``skill_key``; everything that stores a
name goes through ``canonical_skill_name``.

Proficiency levels are stored as plain strings (``native_enum=False``), so SQL
``MAX()`` orders them alphabetically (ADVANCED < BEGINNER < EXPERT <
INTERMEDIATE). Compare levels with ``proficiency_rank`` / ``highest_proficiency``
instead.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from app.shared.enums import ProficiencyLevel

# Letters and digits survive; "+" and "#" too, so C, C++ and C# stay apart.
# Everything else (case, spaces, dots, slashes, hyphens) is ignored, which
# folds "Node.js" / "NodeJS" / "node js" and "CI/CD" / "CICD" together.
_KEY_DROP = re.compile(r"[^\w+#]|_")

# canonical name -> spellings that mean the same technology. Only real
# synonyms belong here; related-but-different tools (Spring vs Spring Boot,
# AWS vs Amazon S3) stay separate.
_ALIASES: dict[str, tuple[str, ...]] = {
    "JavaScript": ("JS", "ECMAScript", "ES6"),
    "TypeScript": ("TS",),
    "Python": ("Python3", "Python 3"),
    "Go": ("Golang",),
    "C#": ("CSharp", "C Sharp"),
    "C++": ("CPP",),
    ".NET": ("dotnet",),
    "Node.js": ("Node", "NodeJS"),
    "React": ("ReactJS", "React.js"),
    "Next.js": ("NextJS",),
    "Vue.js": ("Vue", "VueJS"),
    "Express.js": ("Express", "ExpressJS"),
    "Tailwind CSS": ("Tailwind",),
    "CSS": ("CSS3",),
    "HTML": ("HTML5",),
    "Kubernetes": ("K8s",),
    "PostgreSQL": ("Postgres",),
    "MongoDB": ("Mongo",),
    "AWS": ("Amazon Web Services",),
    "GCP": ("Google Cloud", "Google Cloud Platform"),
    "Azure": ("Microsoft Azure",),
    "Apache Kafka": ("Kafka",),
    "JMeter": ("Apache JMeter",),
    "JPA": ("Java Persistence API",),
    "CI/CD": (
        "Continuous Integration and Continuous Delivery",
        "Continuous Integration and Continuous Deployment",
        "Continuous Integration/Continuous Delivery",
        "Continuous Integration/Continuous Deployment",
    ),
    "REST APIs": ("REST", "REST API", "RESTful", "RESTful API", "RESTful APIs"),
    "Shell Scripting": ("Shell", "Shell Script", "Shell Scripts"),
    "TLS/SSL": ("SSL/TLS",),
    "End-to-End Testing": ("E2E Testing", "E2E"),
    "Internationalization": ("i18n",),
}


def skill_key(name: str) -> str:
    """Identity of a skill: two names with the same key are the same skill."""
    key = _KEY_DROP.sub("", name.casefold())
    return _ALIAS_KEYS.get(key, key)


def canonical_skill_name(name: str) -> str:
    """Name to store: the canonical spelling for known aliases, else the input tidied."""
    tidy = " ".join(name.split())
    return _CANONICAL_BY_KEY.get(skill_key(tidy), tidy)


def is_known_canonical(name: str) -> bool:
    """True when ``name``'s key maps to a curated canonical spelling."""
    return skill_key(name) in _CANONICAL_BY_KEY


_PROFICIENCY_ORDER = (
    ProficiencyLevel.BEGINNER,
    ProficiencyLevel.INTERMEDIATE,
    ProficiencyLevel.ADVANCED,
    ProficiencyLevel.EXPERT,
)
_RANK = {level: i for i, level in enumerate(_PROFICIENCY_ORDER, start=1)}


def to_proficiency(value: ProficiencyLevel | str | None) -> ProficiencyLevel | None:
    if value is None or isinstance(value, ProficiencyLevel):
        return value
    text = str(value).strip().lower()
    try:
        return ProficiencyLevel(text)
    except ValueError:
        return None


def proficiency_rank(value: ProficiencyLevel | str | None) -> int:
    """1 (beginner) .. 4 (expert); 0 for unknown values."""
    level = to_proficiency(value)
    return _RANK.get(level, 0) if level else 0


def highest_proficiency(levels: Iterable[ProficiencyLevel | str | None]) -> ProficiencyLevel | None:
    best: ProficiencyLevel | None = None
    for value in levels:
        level = to_proficiency(value)
        if level and (best is None or _RANK[level] > _RANK[best]):
            best = level
    return best


def _build_alias_tables() -> tuple[dict[str, str], dict[str, str]]:
    alias_keys: dict[str, str] = {}
    canonical_by_key: dict[str, str] = {}
    for canonical, aliases in _ALIASES.items():
        canonical_key = _KEY_DROP.sub("", canonical.casefold())
        canonical_by_key[canonical_key] = canonical
        for alias in aliases:
            alias_key = _KEY_DROP.sub("", alias.casefold())
            if alias_key != canonical_key:
                alias_keys[alias_key] = canonical_key
    return alias_keys, canonical_by_key


_ALIAS_KEYS, _CANONICAL_BY_KEY = _build_alias_tables()
