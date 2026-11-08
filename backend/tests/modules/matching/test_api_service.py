"""Matching v3 API service on a real Postgres: results, resume binding, labels, title families."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from tests.modules.matching.conftest import LOCAL_DB, requires_db

pytestmark = requires_db

if LOCAL_DB:
    from app.core.exceptions import BadRequestError, NotFoundError
    from app.modules.applications.models import Application
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.matching import service
    from app.modules.matching.families.models import JobRoleFamily, JobTitleFamily
    from app.modules.matching.labels.models import MatchLabel
    from app.modules.matching.models import JobMatch
    from app.modules.matching.schemas import MatchLabelCreate
    from app.modules.resumes.models import Document, Resume
    from app.shared.enums import ApplicationStatus, Role

NOW = datetime.now(timezone.utc)


async def _seed(db, *, role=None):
    user = User(id=1, email="u@example.com", hashed_password="x", full_name="U", role=role or Role.USER)
    other = User(id=2, email="o@example.com", hashed_password="x", full_name="O")
    db.add_all([user, other])
    # job id -> (title, days ago, expired)
    for job_id, (title, days, expired) in {
        1: ("Java Developer", 1, False), 2: ("QA Engineer", 2, False), 3: ("Data Engineer", 3, False),
        4: ("PLC Engineer", 4, False), 5: ("Backend Engineer", 5, False), 6: ("Old Developer", 2, True),
        7: ("Developer (Japanese)", 6, False), 8: ("Queued Developer", 1, False),
    }.items():
        db.add(SeekJob(id=job_id, source_id=f"s{job_id}", title=title, listed_at=NOW - timedelta(days=days),
                       is_expired=expired, location_label="Christchurch"))
    await db.flush()
    db.add(Document(id="doc1", root_id="doc1", content="resume", content_hash="h", created_by=1))
    await db.flush()
    db.add(Resume(id="res1", user_id=1, document_id="doc1", title="Java", is_draft=False, is_deleted=False,
                  role_family="software_dev", role_family_source="auto"))
    await db.flush()

    def match(job_id, status, tier=None, **extra):
        defaults = {"origin": "new_job", "job_family": "software_dev", "families_version": "f2",
                    "family_relation": "same", "location_check": "matched", "candidate_resume_ids": ["res1"]}
        if status == "rated":
            extra.setdefault("resume_id", "res1")
        return JobMatch(id=f"jm{job_id}", user_id=1, job_id=job_id, status=status, tier=tier,
                        tier_reason=f"tier {tier}" if tier else None, **{**defaults, **extra})
    db.add_all([
        match(1, "rated", "A", judgment={"tech_items": [{"requirement": "Java"}], "relevant_years": 8,
                                         "other_constraints": [{"requirement": "On call", "quote": "on call"}]},
              model="m", prompt_version="v2"),
        match(2, "rated", "B"),
        match(3, "rated", "C"),
        match(4, "rated", "D"),
        match(5, "rejected", reject_code="LOCATION", reject_reason="Outside", location_check="rejected"),
        match(6, "rated", "A"),  # expired job: hidden
        match(7, "rejected", "B", resume_id="res1", reject_code="LANGUAGE", reject_reason="Japanese required",
              reject_quote="Fluent Japanese required"),
        match(8, "queued"),
    ])
    db.add(Application(id="app1", user_id=1, job_id=1, source_resume_id="res1", status=ApplicationStatus.APPLIED))
    await db.commit()
    return user, other


@pytest.mark.asyncio
async def test_list_matches_views_tiers_and_counts(session):
    user, _ = await _seed(session)
    result = await service.list_matches(session, user)
    assert [i.job.id for i in result.items] == [1, 2] and result.total == 2
    first = result.items[0]
    assert first.match.tier == "A" and first.match.recommended_resume.id == "res1"
    assert first.match.application_status == "APPLIED" and first.job.has_application
    assert first.match.label is None  # labels are for admins only
    assert result.counts.model_dump() == {"A": 1, "B": 1, "C": 1, "rejected": 2, "pending": 1}

    with_c = await service.list_matches(session, user, tiers=["A", "B", "C"])
    assert [i.job.id for i in with_c.items] == [1, 2, 3]
    with pytest.raises(BadRequestError):
        await service.list_matches(session, user, tiers=["D"])  # never for users

    rejected = await service.list_matches(session, user, view="rejected")
    assert {i.job.id: i.match.reject_code for i in rejected.items} == {5: "LOCATION", 7: "LANGUAGE"}
    assert rejected.items[1].match.reject_quote == "Fluent Japanese required"

    page = await service.list_matches(session, user, limit=1, offset=1)
    assert [i.job.id for i in page.items] == [2] and page.total == 2


@pytest.mark.asyncio
async def test_admin_sees_d_and_labels(session):
    admin, _ = await _seed(session, role=Role.ADMIN)
    result = await service.list_matches(session, admin, tiers=["D"])
    assert [i.job.id for i in result.items] == [4]
    assert (await service.get_match_detail(session, admin, 4)).tier == "D"

    first = await service.create_label(session, admin, MatchLabelCreate(job_id=2, label="A", reason_tags=["tech"]))
    second = await service.create_label(session, admin, MatchLabelCreate(job_id=2, label="B", note="on reflection"))
    rows = {r.id: r for r in (await session.execute(select(MatchLabel))).scalars()}
    assert rows[first.id].superseded_by == second.id and rows[second.id].superseded_by is None
    assert rows[first.id].reason_tags == ["TECH"]
    assert (rows[second.id].predicted_tier, rows[second.id].job_match_id) == ("B", "jm2")
    listed = await service.list_matches(session, admin)
    assert next(i for i in listed.items if i.job.id == 2).match.label.label == "B"

    # "Should have matched": a job without any result can be labeled too.
    session.add(SeekJob(id=9, source_id="s9", title="Missed", listed_at=NOW))
    await session.commit()
    missed = await service.create_label(session, admin, MatchLabelCreate(job_id=9, label="A"))
    row = await session.get(MatchLabel, missed.id)
    assert row.job_match_id is None and row.predicted_status is None
    with pytest.raises(BadRequestError):
        await service.create_label(session, admin, MatchLabelCreate(job_id=2, label="A", reason_tags=["NOPE"]))
    with pytest.raises(NotFoundError):
        await service.create_label(session, admin, MatchLabelCreate(job_id=999, label="A"))


@pytest.mark.asyncio
async def test_match_detail(session):
    user, other = await _seed(session)
    detail = await service.get_match_detail(session, user, 1)
    assert detail.tech_items == [{"requirement": "Java"}] and detail.relevant_years == 8
    assert detail.other_constraints[0]["requirement"] == "On call"
    assert detail.prompt_version == "v2" and detail.application_status == "APPLIED"
    assert await service.get_match_detail(session, user, 4) is None  # D hidden from users
    assert await service.get_match_detail(session, other, 1) is None  # someone else's result


@pytest.mark.asyncio
async def test_set_resume_role_family(session):
    user, other = await _seed(session)
    before = (await session.get(Resume, "res1")).updated_at
    result = await service.set_resume_role_family(session, user, "res1", "qa_test")
    assert (result.role_family, result.role_family_source) == ("qa_test", "user")
    resume = await session.get(Resume, "res1")
    assert resume.role_family_version and resume.updated_at > before  # drives backfill origin
    assert (await service.set_resume_role_family(session, user, "res1", None)).role_family is None
    with pytest.raises(BadRequestError):
        await service.set_resume_role_family(session, user, "res1", "astronaut")
    with pytest.raises(NotFoundError):
        await service.set_resume_role_family(session, other, "res1", "qa_test")
    assert {f.key for f in service.list_role_families()} >= {"software_dev", "app_support"}


@pytest.mark.asyncio
async def test_title_family_admin_tools(session):
    admin, _ = await _seed(session, role=Role.ADMIN)
    session.add_all([
        JobTitleFamily(id="t1", title_key="java developer", example_title="Java Developer", status="classified",
                       role_family="software_dev", source="llm", families_version="f2", classifier_version="c1"),
        JobTitleFamily(id="t2", title_key="plc engineer", example_title="PLC Engineer", status="ambiguous",
                       source="llm", families_version="f2", classifier_version="c1"),
        JobRoleFamily(job_id=1, title_key="java developer", status="classified", role_family="software_dev",
                      method="title_cache", families_version="f2"),
        JobRoleFamily(job_id=4, title_key="plc engineer", status="classified", role_family="software_dev",
                      method="jd_read", families_version="f2"),
    ])
    await session.commit()

    listed = await service.list_title_families(session, q="PLC")
    assert [i.title_key for i in listed.items] == ["plc engineer"] and listed.items[0].job_count == 1
    assert (await service.list_title_families(session, status="classified")).total == 1

    result = await service.update_title_family(session, admin, "Senior PLC Engineer", "other_engineering")
    assert result.item.source == "admin" and result.item.role_family == "other_engineering"
    assert (result.jobs_changed, result.jobs_to_pending) == (1, 0)
    assert (await session.get(JobRoleFamily, 4)).role_family == "other_engineering"
    # Existing results are not re-judged.
    assert (await session.get(JobMatch, "jm4")).tier == "D"

    result = await service.update_title_family(session, admin, "java developer", None)
    assert result.item.status == "ambiguous" and result.jobs_to_pending == 1
    with pytest.raises(BadRequestError):
        await service.update_title_family(session, admin, "java developer", "astronaut")
