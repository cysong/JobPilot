"""Reject existing matches for jobs from crowd / paid-per-task platforms.

The company blocklist (app/modules/matching/config/non_employment.yaml) rejects
new jobs at enqueue. Results judged before it existed still show such jobs as
A / B. This applies the same rule to them, without calling the LLM:

- rated / queued / failed matches whose job's advertiser or company is on the
  list become status=rejected, reject_code=NOT_EMPLOYMENT;
- location rejections and rows already NOT_EMPLOYMENT are left alone;
- the previous status / tier go to validation.reclassified, the judgment is kept.

Dry run by default (rolled back, summary printed). Pass --apply to commit.

    uv run --with greenlet python scripts/reject_non_employment_matches.py [--user-id 1] [--apply]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import async_session_factory  # noqa: E402
from app.modules.jobs.models import SeekJob  # noqa: E402
from app.modules.matching.employment import NON_EMPLOYMENT_REASON, is_non_employment_company  # noqa: E402
from app.modules.matching.models import JobMatch, JobMatchStatus, RejectCode  # noqa: E402


async def reclassify(db, *, user_id: int | None = None) -> list[tuple[JobMatch, str]]:
    """Mark the matches (not committed). Returns [(match, company)] that changed."""
    stmt = (
        select(JobMatch, SeekJob.advertiser_name, SeekJob.company_name)
        .join(SeekJob, SeekJob.id == JobMatch.job_id)
        .where(JobMatch.reject_code.is_distinct_from(RejectCode.LOCATION),
               JobMatch.reject_code.is_distinct_from(RejectCode.NOT_EMPLOYMENT),
               JobMatch.status != JobMatchStatus.SKIPPED_EXPIRED)
    )
    if user_id is not None:
        stmt = stmt.where(JobMatch.user_id == user_id)
    changed = []
    now = datetime.now(timezone.utc).isoformat()
    for match, advertiser, company in (await db.execute(stmt)).all():
        if not is_non_employment_company(advertiser, company):
            continue
        match.validation = {**(match.validation or {}), "reclassified": {
            "rule": "non_employment_blocklist", "from_status": match.status, "from_tier": match.tier,
            "from_reject_code": match.reject_code, "at": now}}
        match.status = JobMatchStatus.REJECTED
        match.reject_code = RejectCode.NOT_EMPLOYMENT
        match.reject_reason = NON_EMPLOYMENT_REASON
        match.reject_quote = None
        match.next_attempt_at = None
        changed.append((match, advertiser or company or ""))
    return changed


async def main(user_id: int | None, apply: bool) -> None:
    async with async_session_factory() as db:
        changed = await reclassify(db, user_id=user_id)
        before = Counter((m.validation["reclassified"]["from_status"], m.validation["reclassified"]["from_tier"])
                         for m, _ in changed)
        print(f"matches to reject as NOT_EMPLOYMENT: {len(changed)}")
        print("  by previous status / tier:", dict(sorted(before.items(), key=str)))
        print("  by company:", dict(Counter(c for _, c in changed).most_common()))
        print("  by user:", dict(Counter(m.user_id for m, _ in changed)))
        if apply:
            await db.commit()
            print("applied")
        else:
            await db.rollback()
            print("dry run: rolled back (pass --apply to commit)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.user_id, args.apply))
