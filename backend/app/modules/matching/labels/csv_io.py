"""Export judged pairs for offline labeling and import the filled-in labels.

Stage 1 has no labeling UI, so admins label a CSV. Import is append-only: a new
label supersedes the labeler's previous current label for the same pair.
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matching.evaluation.metrics import outcome
from app.modules.matching.evaluation.models import MatchEvalPrediction, MatchEvalRun
from app.modules.matching.evaluation.runner import load_run_rows
from app.modules.matching.labels.models import LABEL_VALUES, REASON_TAGS, MatchLabel
from app.shared.utils import generate_id

EXPORT_COLUMNS = [
    "user_id", "job_id", "item_kind", "title", "company", "predicted", "tech_level",
    "experience_level", "tier_reason", "label", "reason_tags", "note",
]
LABEL_GUIDE = (
    "label: A (tech match + relevant experience) | B (worth a try) | C (not recommended) | "
    "D (different track) | REJECT (hard condition unmet). reason_tags: " + "|".join(REASON_TAGS)
)


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped_blank: int
    errors: list[str]


async def export_for_labeling(db: AsyncSession, run_id: str, path: Path, *, limit: int = 50,
                              seed: int = 7) -> int:
    rows = [r for r in await load_run_rows(db, run_id) if r["repeat_index"] == 0 and r["judged"]]
    rng = random.Random(seed)
    # Interleave kinds so a small sample still covers random, applied and filtered-miss items.
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        by_kind.setdefault(r["item_kind"], []).append(r)
    for bucket in by_kind.values():
        rng.shuffle(bucket)
    picked: list[dict] = []
    while len(picked) < limit and any(by_kind.values()):
        for kind in sorted(by_kind):
            if by_kind[kind] and len(picked) < limit:
                picked.append(by_kind[kind].pop())

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# {LABEL_GUIDE}\n")
        writer = csv.DictWriter(fh, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for r in picked:
            judgment = r.get("judgment") or {}
            writer.writerow({
                "user_id": r["user_id"], "job_id": r["job_id"], "item_kind": r["item_kind"],
                "title": r.get("title") or "", "company": r.get("company") or "",
                "predicted": outcome(r), "tech_level": judgment.get("tech_level", ""),
                "experience_level": judgment.get("experience_level", ""),
                "tier_reason": r.get("tier_reason") or "", "label": "", "reason_tags": "", "note": "",
            })
    return len(picked)


def _read_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        lines = [line for line in fh if not line.startswith("#")]
    return csv.DictReader(lines)


async def import_labels(db: AsyncSession, path: Path, *, labeled_by: int, run_id: str | None = None) -> ImportResult:
    predictions: dict[tuple[int, int], MatchEvalPrediction] = {}
    run_config: dict = {}
    if run_id:
        run = await db.get(MatchEvalRun, run_id)
        run_config = run.config if run else {}
        for p in (await db.execute(
            select(MatchEvalPrediction).where(MatchEvalPrediction.run_id == run_id,
                                              MatchEvalPrediction.repeat_index == 0)
        )).scalars():
            predictions[(p.user_id, p.job_id)] = p

    imported = skipped = 0
    errors: list[str] = []
    for line_no, row in enumerate(_read_rows(path), start=2):
        label = (row.get("label") or "").strip().upper()
        if not label:
            skipped += 1
            continue
        if label not in LABEL_VALUES:
            errors.append(f"line {line_no}: invalid label {label!r}")
            continue
        tags = [t.strip().upper() for t in (row.get("reason_tags") or "").replace(",", "|").split("|") if t.strip()]
        bad_tags = [t for t in tags if t not in REASON_TAGS]
        if bad_tags:
            errors.append(f"line {line_no}: invalid reason_tags {bad_tags}")
            continue
        try:
            user_id, job_id = int(row["user_id"]), int(row["job_id"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"line {line_no}: missing user_id/job_id")
            continue

        pred = predictions.get((user_id, job_id))
        new_id = generate_id("ml")
        db.add(MatchLabel(
            id=new_id, user_id=user_id, job_id=job_id, label=label, reason_tags=tags,
            note=(row.get("note") or "").strip() or None, source="import", labeled_by=labeled_by,
            predicted_status=pred.status if pred else None,
            predicted_tier=pred.tier if pred else None,
            predicted_prompt_version=run_config.get("prompt_version"),
            predicted_model=run_config.get("model"),
            predicted_snapshot=(pred.judgment or {}).get("judgment") if pred else None,
        ))
        await db.flush()
        await db.execute(
            update(MatchLabel)
            .where(MatchLabel.user_id == user_id, MatchLabel.job_id == job_id,
                   MatchLabel.labeled_by == labeled_by, MatchLabel.superseded_by.is_(None),
                   MatchLabel.id != new_id)
            .values(superseded_by=new_id)
        )
        imported += 1
    await db.commit()
    return ImportResult(imported, skipped, errors)
