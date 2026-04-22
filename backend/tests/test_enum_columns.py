"""Guard tests for SQLAlchemy enum column conventions.

These were added after an incident where Application.status was declared
without values_callable, causing the DB to silently store enum member
NAMES instead of values. The mismatch only surfaced months later when
the application_status_history table started failing Pydantic validation
on read.

If these tests fail, the offending column is missing values_callable —
fix by using `app.shared.sqlalchemy_helpers.EnumColumn` instead of a raw
`SQLEnum(...)`.
"""
from __future__ import annotations

import importlib
import pkgutil

from sqlalchemy import Enum as SQLEnum

# Import every module under app.modules to populate Base.metadata before
# we walk the tables. Without this, models that no test has touched are
# absent from the metadata registry.
import app.modules as _modules_pkg
from app.shared.base_model import Base


def _import_all_models() -> None:
    for module_info in pkgutil.walk_packages(_modules_pkg.__path__, prefix="app.modules."):
        if module_info.name.endswith(".models"):
            importlib.import_module(module_info.name)


# Known pre-existing offenders not yet migrated to EnumColumn. Each one
# has the same latent bug (DB stores enum NAME instead of VALUE because
# values_callable is missing) but hasn't blown up yet because nothing
# round-trips through Pydantic with strict enum validation. Migrate one
# at a time and remove from this list — do NOT add new entries.
_KNOWN_PENDING: set[str] = {
    "documents.format",
    "resume_skills.proficiency_level",
    "user_skills.proficiency_level",
    "user_skills.manual_proficiency",
    "task_executions.status",
    "ai_calls.status",
}


def test_all_sqlenum_columns_have_values_callable() -> None:
    _import_all_models()

    offenders: list[str] = []
    unexpected_clean: list[str] = []
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if not isinstance(col.type, SQLEnum):
                continue
            qualified = f"{table.name}.{col.name}"
            if col.type.values_callable is None:
                if qualified not in _KNOWN_PENDING:
                    offenders.append(qualified)
            else:
                if qualified in _KNOWN_PENDING:
                    unexpected_clean.append(qualified)

    assert not offenders, (
        "SQLEnum columns missing values_callable (use EnumColumn helper): "
        + ", ".join(offenders)
    )
    assert not unexpected_clean, (
        "These columns are now clean — remove them from _KNOWN_PENDING: "
        + ", ".join(unexpected_clean)
    )
