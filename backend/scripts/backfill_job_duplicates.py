"""Group existing reposts of the same job and mark existing results as duplicates.

New jobs are grouped when they are discovered (app.modules.matching.duplicates);
this script does the same for jobs registered before that existed. Nothing is
re-judged and no LLM is called:

1. Jobs: every job_role_families row whose job was listed in the last --days is
   compared with the others (oldest first); a repost gets duplicate_of = the
   group's first listing.
2. Results: within each group, the user's judged results (location rejections
   aside) keep their tiers; the best one (rated before rejected, best tier, judged
   first) stays as is and the others get duplicate_of = that result. The match list
   then shows one entry per group.

Dry run by default: one transaction rolled back at the end, with a summary and
sample groups printed. Pass --apply to commit.

    uv run --with greenlet python scripts/backfill_job_duplicates.py [--days 60] [--apply]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import async_session_factory  # noqa: E402
from app.modules.jobs.models import SeekJob  # noqa: E402
from app.modules.matching.duplicates import Listing, assign_duplicates, best_result_key  # noqa: E402
from app.modules.matching.families.models import JobRoleFamily  # noqa: E402
from app.modules.matching.models import JobMatch, JobMatchStatus, RejectCode  # noqa: E402
from app.modules.matching.text import html_to_text  # noqa: E402


async def group_jobs(db, days: int) -> tuple[dict[int, int], dict[int, str]]:
    """Returns ({job_id: leader job_id} for all grouped jobs, {job_id: title} for printing)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(
        select(JobRoleFamily.job_id, JobRoleFamily.title_key, JobRoleFamily.duplicate_of, SeekJob.title,
               SeekJob.advertiser_name, SeekJob.company_name, SeekJob.listed_at, SeekJob.content,
               SeekJob.abstract, SeekJob.source, SeekJob.location_label)
        .join(SeekJob, SeekJob.id == JobRoleFamily.job_id)
        .where(SeekJob.listed_at >= since)
    )).all()
    listings = [Listing(job_id=r.job_id, title_key=r.title_key, title=r.title,
                        companies=(r.advertiser_name, r.company_name), listed_at=r.listed_at,
                        text=html_to_text(r.content) or (r.abstract or ""), duplicate_of=r.duplicate_of)
                for r in rows]
    already = {j.job_id: j.duplicate_of for j in listings if j.duplicate_of is not None}
    # Leaders already chosen stay leaders; everything ungrouped is re-checked oldest first.
    existing = [j for j in listings if j.duplicate_of is None and j.job_id in set(already.values())]
    fresh = [j for j in listings if j.duplicate_of is None and j.job_id not in set(already.values())]
    found = assign_duplicates(fresh, existing)
    for job_id, leader in found.items():
        await db.execute(update(JobRoleFamily).where(JobRoleFamily.job_id == job_id).values(duplicate_of=leader))
    labels = {r.job_id: f"{r.title} · {r.advertiser_name or r.company_name} · {r.source} · {r.location_label}"
              for r in rows}
    print(f"jobs listed in the last {days} days: {len(rows)}; already grouped: {len(already)}; "
          f"newly grouped: {len(found)} into {len(set(found.values()))} leaders")
    return {**already, **found}, labels


async def merge_results(db, leaders: dict[int, int], labels: dict[int, str], samples: int) -> None:
    groups: dict[int, set[int]] = defaultdict(set)
    for job_id, leader in leaders.items():
        groups[leader].update((job_id, leader))
    member_of = {job_id: leader for leader, members in groups.items() for job_id in members}
    matches = (await db.execute(
        select(JobMatch).where(
            JobMatch.job_id.in_(list(member_of)),
            JobMatch.status.in_([JobMatchStatus.RATED, JobMatchStatus.REJECTED]),
            JobMatch.reject_code.is_distinct_from(RejectCode.LOCATION),
        )
    )).scalars().all()
    by_group: dict[tuple[int, int], list[JobMatch]] = defaultdict(list)
    for match in matches:
        by_group[(match.user_id, member_of[match.job_id])].append(match)

    marked = mixed = 0
    shown = 0
    for (user_id, leader), rows in sorted(by_group.items()):
        if len(rows) < 2:
            continue
        keeper = min(rows, key=best_result_key)
        tiers = sorted({m.tier or m.status for m in rows})
        if len(tiers) > 1:
            mixed += 1
        for match in rows:
            if match.id != keeper.id and match.duplicate_of is None:
                match.duplicate_of = keeper.id
                marked += 1
        if shown < samples:
            shown += 1
            print(f"  user {user_id} · keep job {keeper.job_id} ({keeper.tier or keeper.status}) "
                  f"· {len(rows)} results {tiers} · {labels.get(keeper.job_id, '')}")
    print(f"results marked as duplicates: {marked}; groups with differing tiers: {mixed}")


async def main(days: int, apply: bool, samples: int) -> None:
    async with async_session_factory() as db:
        leaders, labels = await group_jobs(db, days)
        await merge_results(db, leaders, labels, samples)
        if apply:
            await db.commit()
            print("applied")
        else:
            await db.rollback()
            print("dry run: rolled back (pass --apply to commit)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=60, help="only jobs listed in the last N days")
    parser.add_argument("--samples", type=int, default=15, help="sample groups to print")
    parser.add_argument("--apply", action="store_true", help="commit the changes")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.apply, args.samples))
