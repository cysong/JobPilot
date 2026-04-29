"""Guard test for BRIEF_COLUMNS / Job schema synchronization.

JobRepository.BRIEF_COLUMNS drives the load_only narrowing applied by
list/card endpoints (list_jobs, list_my_matches, find_similar_jobs,
list_saved_jobs, etc.). It must cover every column-backed field of
JobBase / JobBriefInfo, otherwise reading a missing field in the
response serializer triggers a lazy load (or worse, MissingGreenlet
on async sessions).

If this test fails, add the missing columns to BRIEF_COLUMNS in
app/modules/jobs/repository.py.
"""
from __future__ import annotations

from app.modules.jobs.repository import BRIEF_COLUMNS
from app.modules.jobs.schemas import JobBase, JobBriefInfo


# Fields the service layer overlays onto the ORM instance after loading
# (set by code, not present as SeekJob columns).
_SERVICE_OVERLAY_FIELDS = {"is_viewed", "last_viewed_at", "has_application"}

# Pydantic field name -> set of underlying SeekJob column names, for
# non-direct mappings (hybrid_property aliases, etc.).
_FIELD_TO_COLUMNS = {
    # is_expired uses validation_alias="effective_is_expired", a
    # hybrid_property that combines these two real columns.
    "is_expired": {"is_expired", "manual_expired"},
}


def _required_columns_for(model_cls) -> set[str]:
    cols: set[str] = set()
    for name in model_cls.model_fields:
        if name in _SERVICE_OVERLAY_FIELDS:
            continue
        cols.update(_FIELD_TO_COLUMNS.get(name, {name}))
    return cols


def _declared_brief_columns() -> set[str]:
    return {col.key for col in BRIEF_COLUMNS}


def test_brief_columns_covers_jobbase():
    required = _required_columns_for(JobBase)
    declared = _declared_brief_columns()
    missing = required - declared
    assert not missing, (
        f"BRIEF_COLUMNS missing for JobBase fields: {sorted(missing)}. "
        "Update BRIEF_COLUMNS in app/modules/jobs/repository.py to keep "
        "list/card responses lazy-load free."
    )


def test_brief_columns_covers_jobbriefinfo():
    required = _required_columns_for(JobBriefInfo)
    declared = _declared_brief_columns()
    missing = required - declared
    assert not missing, (
        f"BRIEF_COLUMNS missing for JobBriefInfo fields: {sorted(missing)}. "
        "Update BRIEF_COLUMNS in app/modules/jobs/repository.py."
    )
