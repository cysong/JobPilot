"""Role family classification of job titles and ambiguous jobs (docs/job_matching_v3_design.md §4.3).

Pure parsing/prompt helpers plus async orchestration over the gateway and DB.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Protocol, Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from agent_configs.schemas import JobFamilyReading, TitleClassificationBatch
from app.core.config import settings
from app.core.llm.types import ModelOverride
from app.modules.jobs.models import SeekJob
from app.modules.matching.families.models import (
    JobFamilyMethod,
    JobFamilyStatus,
    JobRoleFamily,
    JobTitleFamily,
    TitleFamilySource,
    TitleFamilyStatus,
)
from app.modules.matching.families.normalize import normalize_title
from app.modules.matching.families.registry import RoleFamilyRegistry, get_registry
from app.modules.matching.text import html_to_text
from app.shared.utils import generate_id

logger = structlog.get_logger()

TITLE_CLASSIFIER_AGENT = "title_classifier"
JOB_FAMILY_READER_AGENT = "job_family_reader"
CLASSIFIER_VERSION = f"{TITLE_CLASSIFIER_AGENT}:{TitleClassificationBatch.__version__}"
MAX_JD_READ_ATTEMPTS = 3


class Gateway(Protocol):
    async def call(self, agent_id: str, input_data: str, context: dict | None = None,
                   model_override: ModelOverride | None = None) -> Any: ...


@dataclass(frozen=True)
class TitleToClassify:
    title_key: str
    example_title: str


@dataclass(frozen=True)
class TitleResult:
    title_key: str
    status: str  # classified | ambiguous
    role_family: str | None


# ------------------------------------------------------------------ pure helpers


def build_title_batch_input(registry: RoleFamilyRegistry, items: Sequence[TitleToClassify]) -> str:
    return json.dumps(
        {
            "families": registry.catalog_for_prompt(),
            "titles": [{"title_key": i.title_key, "example_title": i.example_title} for i in items],
        },
        ensure_ascii=False,
    )


def parse_title_batch(
    output: TitleClassificationBatch | dict, requested: Iterable[str], registry: RoleFamilyRegistry
) -> list[TitleResult]:
    """Map classifier output back to requested keys.

    Keys the model skipped are left out (they stay unclassified and are retried
    later). Unknown family keys are treated as ambiguous rather than trusted.
    """
    batch = output if isinstance(output, TitleClassificationBatch) else TitleClassificationBatch.model_validate(output)
    wanted = set(requested)
    results: dict[str, TitleResult] = {}
    for item in batch.items:
        if item.title_key not in wanted or item.title_key in results:
            continue
        if not item.ambiguous and registry.is_valid(item.role_family):
            results[item.title_key] = TitleResult(item.title_key, TitleFamilyStatus.CLASSIFIED, item.role_family)
        else:
            results[item.title_key] = TitleResult(item.title_key, TitleFamilyStatus.AMBIGUOUS, None)
    return list(results.values())


def build_jd_read_input(registry: RoleFamilyRegistry, title: str, content_html: str | None,
                        abstract: str | None = None, char_limit: int | None = None) -> str:
    limit = char_limit or settings.JD_READ_CHAR_LIMIT
    text = html_to_text(content_html) or (abstract or "")
    return json.dumps(
        {"families": registry.catalog_for_prompt(), "title": title, "description_excerpt": text[:limit]},
        ensure_ascii=False,
    )


def parse_jd_read(output: JobFamilyReading | dict, registry: RoleFamilyRegistry) -> JobFamilyReading:
    reading = output if isinstance(output, JobFamilyReading) else JobFamilyReading.model_validate(output)
    if not registry.is_valid(reading.role_family):
        raise ValueError(f"job_family_reader returned unknown family {reading.role_family!r}")
    return reading


def classifier_override() -> ModelOverride:
    return ModelOverride(provider=settings.MATCH_LLM_PROVIDER, model=settings.TITLE_CLASSIFIER_MODEL)


# ------------------------------------------------------------------ DB + LLM orchestration


async def classify_titles(
    db: AsyncSession,
    gateway: Gateway,
    items: Sequence[TitleToClassify],
    *,
    task_id: str | None = None,
    registry: RoleFamilyRegistry | None = None,
    batch_size: int | None = None,
) -> int:
    """Classify title keys in batches and upsert the cache. Returns rows written.

    Admin-sourced rows are never overwritten.
    """
    registry = registry or get_registry()
    size = batch_size or settings.TITLE_CLASSIFIER_BATCH_SIZE
    override = classifier_override()
    written = 0
    for start in range(0, len(items), size):
        batch = items[start:start + size]
        context: dict = {"operation": "title_family_classification"}
        if task_id:
            context["task_id"] = task_id
        try:
            output = await gateway.call(
                TITLE_CLASSIFIER_AGENT, build_title_batch_input(registry, batch),
                context=context, model_override=override,
            )
            results = parse_title_batch(output, [i.title_key for i in batch], registry)
        except Exception as exc:  # noqa: BLE001 - one bad batch must not stop the run
            logger.warning("title_batch_failed", size=len(batch), error=str(exc))
            continue
        examples = {i.title_key: i.example_title for i in batch}
        written += await _upsert_title_results(db, results, examples, registry.version, override.model)
        await db.commit()
    return written


async def _upsert_title_results(
    db: AsyncSession, results: Sequence[TitleResult], examples: dict[str, str],
    families_version: str, model: str | None,
) -> int:
    if not results:
        return 0
    rows = [
        {
            "id": generate_id("jtf"),
            "title_key": r.title_key,
            "example_title": examples.get(r.title_key, r.title_key)[:500],
            "status": r.status,
            "role_family": r.role_family,
            "source": TitleFamilySource.LLM,
            "families_version": families_version,
            "classifier_version": CLASSIFIER_VERSION,
            "model": model,
        }
        for r in results
    ]
    stmt = pg_insert(JobTitleFamily).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[JobTitleFamily.title_key],
        set_={
            "status": stmt.excluded.status,
            "role_family": stmt.excluded.role_family,
            "families_version": stmt.excluded.families_version,
            "classifier_version": stmt.excluded.classifier_version,
            "model": stmt.excluded.model,
            "updated_at": stmt.excluded.updated_at,
        },
        where=JobTitleFamily.source != TitleFamilySource.ADMIN,
    )
    await db.execute(stmt)
    return len(rows)


async def register_jobs(db: AsyncSession, jobs: Sequence[tuple[int, str]]) -> int:
    """Insert pending job_role_families rows for (job_id, title); existing rows are kept."""
    if not jobs:
        return 0
    rows = [{"job_id": job_id, "title_key": normalize_title(title)} for job_id, title in jobs]
    result = await db.execute(
        pg_insert(JobRoleFamily).values(rows).on_conflict_do_nothing(index_elements=[JobRoleFamily.job_id])
    )
    return result.rowcount or 0


async def classify_missing_titles(db: AsyncSession, gateway: Gateway, *, task_id: str | None = None,
                                  registry: RoleFamilyRegistry | None = None) -> int:
    """Classify every title_key used by a pending job that is not cached yet."""
    rows = (await db.execute(
        select(JobRoleFamily.title_key, SeekJob.title)
        .join(SeekJob, SeekJob.id == JobRoleFamily.job_id)
        .outerjoin(JobTitleFamily, JobTitleFamily.title_key == JobRoleFamily.title_key)
        .where(JobRoleFamily.status == JobFamilyStatus.PENDING, JobTitleFamily.id.is_(None))
    )).all()
    examples: dict[str, str] = {}
    for key, title in rows:
        examples.setdefault(key, title)
    items = [TitleToClassify(k, v) for k, v in examples.items()]
    return await classify_titles(db, gateway, items, task_id=task_id, registry=registry)


async def resolve_pending_jobs(
    db: AsyncSession, gateway: Gateway, *, task_id: str | None = None,
    registry: RoleFamilyRegistry | None = None, limit: int | None = None,
) -> dict[str, int]:
    """Settle pending jobs from the title cache; read the JD for ambiguous titles."""
    registry = registry or get_registry()
    stmt = (
        select(JobRoleFamily, JobTitleFamily, SeekJob.title, SeekJob.content, SeekJob.abstract)
        .join(SeekJob, SeekJob.id == JobRoleFamily.job_id)
        .join(JobTitleFamily, JobTitleFamily.title_key == JobRoleFamily.title_key)
        .where(JobRoleFamily.status == JobFamilyStatus.PENDING)
        .order_by(SeekJob.listed_at.desc().nullslast())
    )
    if limit:
        stmt = stmt.limit(limit)
    counts = {"title_cache": 0, "jd_read": 0, "failed": 0}
    override = classifier_override()
    for job_family, title_family, title, content, abstract in (await db.execute(stmt)).all():
        if title_family.status == TitleFamilyStatus.CLASSIFIED:
            job_family.status = JobFamilyStatus.CLASSIFIED
            job_family.role_family = title_family.role_family
            job_family.method = JobFamilyMethod.TITLE_CACHE
            job_family.families_version = registry.version
            counts["title_cache"] += 1
            continue

        context: dict = {"operation": "job_family_jd_read"}
        if task_id:
            context["task_id"] = task_id
        job_family.attempts += 1
        try:
            output = await gateway.call(
                JOB_FAMILY_READER_AGENT, build_jd_read_input(registry, title, content, abstract),
                context=context, model_override=override,
            )
            reading = parse_jd_read(output, registry)
        except Exception as exc:  # noqa: BLE001
            job_family.error = str(exc)[:2000]
            if job_family.attempts >= MAX_JD_READ_ATTEMPTS:
                job_family.status = JobFamilyStatus.FAILED
                counts["failed"] += 1
            continue
        job_family.status = JobFamilyStatus.CLASSIFIED
        job_family.role_family = reading.role_family
        job_family.reason = reading.reason
        job_family.method = JobFamilyMethod.JD_READ
        job_family.families_version = registry.version
        job_family.ai_call_id = context.get("ai_call_id")
        job_family.error = None
        counts["jd_read"] += 1
        await db.commit()
    await db.commit()
    return counts
