"""Append-only admin labels (docs/job_matching_v3_design.md §8.1)."""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matching.labels.models import LABEL_VALUES, REASON_TAGS, MatchLabel
from app.modules.matching.models import JobMatch
from app.shared.utils import generate_id


async def add_label(
    db: AsyncSession,
    *,
    user_id: int,
    job_id: int,
    label: str,
    labeled_by: int,
    source: str,
    reason_tags: Sequence[str] = (),
    note: str | None = None,
    prediction: dict[str, Any] | None = None,
) -> MatchLabel:
    """Insert a label and point the labeler's previous current label for the pair at it.

    ``prediction`` overrides the snapshot of the system result (used by CSV imports from
    evaluation runs); otherwise the pair's live ``job_matches`` row is snapshotted.
    """
    label = label.strip().upper()
    if label not in LABEL_VALUES:
        raise ValueError(f"invalid label {label!r}")
    tags = [t.strip().upper() for t in reason_tags if t.strip()]
    bad = [t for t in tags if t not in REASON_TAGS]
    if bad:
        raise ValueError(f"invalid reason_tags {bad}")

    match = (await db.execute(
        select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job_id)
    )).scalar_one_or_none()
    if prediction is None and match is not None:
        prediction = {"status": match.status, "tier": match.tier, "prompt_version": match.prompt_version,
                      "model": match.model, "snapshot": match.judgment}
    prediction = prediction or {}

    row = MatchLabel(
        id=generate_id("ml"), user_id=user_id, job_id=job_id, job_match_id=match.id if match else None,
        label=label, reason_tags=tags, note=(note or "").strip() or None, source=source, labeled_by=labeled_by,
        predicted_status=prediction.get("status"), predicted_tier=prediction.get("tier"),
        predicted_prompt_version=prediction.get("prompt_version"), predicted_model=prediction.get("model"),
        predicted_snapshot=prediction.get("snapshot"),
    )
    db.add(row)
    await db.flush()
    await db.execute(
        update(MatchLabel)
        .where(MatchLabel.user_id == user_id, MatchLabel.job_id == job_id, MatchLabel.labeled_by == labeled_by,
               MatchLabel.superseded_by.is_(None), MatchLabel.id != row.id)
        .values(superseded_by=row.id)
    )
    return row


async def current_labels(db: AsyncSession, *, user_id: int, job_ids: Sequence[int]) -> dict[int, MatchLabel]:
    """The latest (not superseded) label per job for this user's pairs."""
    if not job_ids:
        return {}
    rows = (await db.execute(
        select(MatchLabel).where(MatchLabel.user_id == user_id, MatchLabel.job_id.in_(list(job_ids)),
                                 MatchLabel.superseded_by.is_(None))
        .order_by(MatchLabel.created_at)
    )).scalars()
    return {r.job_id: r for r in rows}
