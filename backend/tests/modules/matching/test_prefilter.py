"""Tests for job freshness and candidate resume selection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.modules.matching.families.registry import RoleFamilyRegistry
from app.modules.matching.prefilter import ResumeRef, is_job_active, select_candidates

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)

REG = RoleFamilyRegistry.from_dict(
    {
        "version": "t1",
        "families": {
            "software_dev": {"adjacent": ["qa_test", "devops_platform"]},
            "qa_test": {},
            "devops_platform": {},
            "other": {},
        },
    }
)


def _active(**kw):
    defaults = dict(is_expired=False, manual_expired=False, expires_at=None,
                    listed_at=NOW - timedelta(days=1), now=NOW, expiry_days=30)
    defaults.update(kw)
    return is_job_active(**defaults)


def test_flags_override_dates():
    assert _active(is_expired=True) is False
    assert _active(manual_expired=True) is False
    assert _active(is_expired=None) is True


def test_expires_at_takes_precedence_over_listed_at():
    assert _active(expires_at=NOW + timedelta(hours=1), listed_at=NOW - timedelta(days=90)) is True
    assert _active(expires_at=NOW - timedelta(seconds=1), listed_at=NOW) is False


def test_missing_expires_at_uses_expiry_days():
    assert _active(listed_at=NOW - timedelta(days=29, hours=23)) is True
    assert _active(listed_at=NOW - timedelta(days=30, seconds=1)) is False
    assert _active(listed_at=NOW - timedelta(days=40), expiry_days=45) is True


def test_no_dates_at_all_is_inactive():
    assert _active(listed_at=None) is False


def _resume(rid, fam, days_ago=0):
    return ResumeRef(id=rid, role_family=fam, updated_at=NOW - timedelta(days=days_ago))


def test_same_family_wins_over_adjacent():
    sel = select_candidates(
        job_family="software_dev",
        resumes=[_resume("qa", "qa_test"), _resume("java", "software_dev"), _resume("devops", "devops_platform")],
        registry=REG,
        max_candidates=3,
    )
    assert sel.relation == "same"
    assert sel.resume_ids == ("java",)


def test_adjacent_used_only_without_same():
    sel = select_candidates(
        job_family="qa_test",
        resumes=[_resume("java", "software_dev"), _resume("devops", "devops_platform")],
        registry=REG,
        max_candidates=3,
    )
    assert sel.relation == "adjacent"
    assert sel.resume_ids == ("java",)  # devops_platform is not adjacent to qa_test here


def test_unrelated_and_unbound_resumes_never_qualify():
    assert select_candidates(
        job_family="other",
        resumes=[_resume("java", "software_dev"), _resume("none", None)],
        registry=REG,
        max_candidates=3,
    ) is None


def test_caps_to_most_recently_updated():
    sel = select_candidates(
        job_family="software_dev",
        resumes=[_resume(f"r{i}", "software_dev", days_ago=i) for i in range(5)],
        registry=REG,
        max_candidates=3,
    )
    assert sel.resume_ids == ("r0", "r1", "r2")
