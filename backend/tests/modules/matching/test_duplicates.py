"""Reposts of the same job: pure grouping rules."""
from datetime import datetime, timedelta, timezone

from app.modules.matching.duplicates import (
    Listing,
    assign_duplicates,
    is_duplicate,
    same_company,
    seniority_words,
    similarity,
    shingles,
)

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
BODY = " ".join(f"word{i}" for i in range(200))


def _job(job_id, *, title="Senior Java Developer", key="java developer", company="Datacom", days=0, text=BODY):
    return Listing(job_id=job_id, title_key=key, title=title, companies=(company, None),
                   listed_at=T0 + timedelta(days=days), text=text)


def test_similarity_takes_containment_for_truncated_copies():
    full = shingles(BODY)
    half = shingles(" ".join(f"word{i}" for i in range(100)))
    assert similarity(full, full) == 1.0
    assert similarity(full, half) == 1.0  # one platform truncated the text
    assert similarity(full, frozenset()) == 0.0


def test_same_company_accepts_platform_variants():
    assert same_company("Kāinga Ora - Homes and Communities", "Kainga Ora")
    assert same_company("Massey University", "Massey University - Te Kunenga ki Pūrehuroa")
    assert same_company("Gallagher Ltd", "gallagher")
    assert not same_company("datacom1", "Datacom")
    assert not same_company(None, "Datacom")


def test_seniority_words_must_match():
    assert seniority_words("Sr. Java Developer") == seniority_words("Senior Java Developer")
    assert not is_duplicate(_job(2, title="Junior Java Developer"), _job(1))


def test_duplicate_rules():
    assert is_duplicate(_job(2, days=3), _job(1))
    assert not is_duplicate(_job(2, days=31), _job(1))  # outside the window
    assert not is_duplicate(_job(2, key="kotlin developer"), _job(1))  # different title
    other = " ".join(f"word{i}" for i in range(20)) + " " + " ".join(f"other{i}" for i in range(180))
    assert not is_duplicate(_job(2, text=other), _job(1))
    assert not is_duplicate(_job(2, text="too short"), _job(1, text="too short"))


def test_other_company_needs_higher_similarity():
    # 2 of 200 words differ: similarity ~0.95 (containment), enough for the same company only.
    edited = " ".join(f"edit{i}" if i in (60, 140) else f"word{i}" for i in range(200))
    assert is_duplicate(_job(2, text=edited), _job(1))
    assert not is_duplicate(_job(2, text=edited, company="datacom1"), _job(1))
    assert is_duplicate(_job(2, company="datacom1"), _job(1))  # identical text


def test_assign_duplicates_points_at_the_first_listing_without_chains():
    existing = [_job(1)]
    new = [_job(3, days=2), _job(2, days=1), _job(4, key="qa engineer", title="QA Engineer")]
    assert assign_duplicates(new, existing) == {2: 1, 3: 1}


def test_assign_duplicates_within_a_new_batch():
    found = assign_duplicates([_job(5, days=4), _job(4, days=1)], [])
    assert found == {5: 4}
