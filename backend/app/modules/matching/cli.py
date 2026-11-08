"""Command line entry point for matching v3 stage 1 (offline).

    uv run python -m app.modules.matching.cli families classify-titles [--all]
    uv run python -m app.modules.matching.cli families init [--days 30]
    uv run python -m app.modules.matching.cli resumes suggest [--user ID] [--apply]
    uv run python -m app.modules.matching.cli resumes set RESUME_ID FAMILY
    uv run python -m app.modules.matching.cli dataset create --name main --user ID [--random 300] [--filtered-sample 80]
    uv run python -m app.modules.matching.cli run --dataset main@v1 [--model M] [--repeat 2] [--baseline RUN]
    uv run python -m app.modules.matching.cli report RUN_ID
    uv run python -m app.modules.matching.cli compare RUN_A RUN_B
    uv run python -m app.modules.matching.cli labels export --run RUN_ID [--limit 50]
    uv run python -m app.modules.matching.cli labels import --file PATH --labeled-by USER_ID [--run RUN_ID]

LLM-backed commands print what they will do and require --yes before spending.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import distinct, select

import app.models  # noqa: F401  register every ORM model before any query
from app.core.config import settings
from app.core.llm.types import ModelOverride

REPORT_DIR = Path("reports/matching")


def _confirm(args: argparse.Namespace, message: str) -> bool:
    print(message)
    if not args.yes:
        print("Dry run. Re-run with --yes to proceed.")
        return False
    return True


async def _families_classify_titles(args) -> None:
    from app.core.database import async_session_factory
    from app.core.llm.gateway import AgentGateway
    from app.modules.jobs.models import SeekJob
    from app.modules.matching.families.classifier import TitleToClassify, classify_titles
    from app.modules.matching.families.models import JobTitleFamily
    from app.modules.matching.families.normalize import normalize_title

    async with async_session_factory() as db:
        stmt = select(distinct(SeekJob.title))
        if not args.all:
            stmt = stmt.where(SeekJob.listed_at >= datetime.now(timezone.utc) - timedelta(days=args.days))
        titles = (await db.execute(stmt)).scalars().all()
        keys: dict[str, str] = {}
        for title in titles:
            keys.setdefault(normalize_title(title), title)
        cached = set((await db.execute(select(JobTitleFamily.title_key))).scalars())
        todo = [TitleToClassify(k, v) for k, v in keys.items() if k and k not in cached]
        batches = -(-len(todo) // settings.TITLE_CLASSIFIER_BATCH_SIZE)
        if not _confirm(args, f"{len(keys)} distinct title keys, {len(todo)} not cached -> "
                              f"{batches} calls to {settings.TITLE_CLASSIFIER_MODEL}."):
            return
        written = await classify_titles(db, AgentGateway.get(), todo)
        print(f"classified {written} title keys")


async def _families_init(args) -> None:
    from app.core.database import async_session_factory
    from app.core.llm.gateway import AgentGateway
    from app.modules.jobs.models import SeekJob
    from app.modules.matching.families.classifier import (
        classify_missing_titles,
        register_jobs,
        resolve_pending_jobs,
    )

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    async with async_session_factory() as db:
        jobs = (await db.execute(select(SeekJob.id, SeekJob.title).where(SeekJob.listed_at >= since))).all()
        if not _confirm(args, f"Register {len(jobs)} jobs listed since {since.date()}, classify missing titles "
                              f"and read the JD of ambiguous ones ({settings.TITLE_CLASSIFIER_MODEL})."):
            return
        added = await register_jobs(db, [(j.id, j.title) for j in jobs])
        await db.commit()
        gateway = AgentGateway.get()
        titles = await classify_missing_titles(db, gateway)
        counts = await resolve_pending_jobs(db, gateway)
        print(f"registered {added} jobs, classified {titles} titles, resolved {counts}")


async def _resumes_suggest(args) -> None:
    from app.core.database import async_session_factory
    from app.core.llm.gateway import AgentGateway
    from app.modules.matching.families.resume_binding import bind_resume_family, suggest_resume_families

    async with async_session_factory() as db:
        suggestions = await suggest_resume_families(db, AgentGateway.get(), user_id=args.user)
        for s in suggestions:
            print(f"{s.resume_id}  user={s.user_id}  {s.title!r:30}  current={s.current or '-'}"
                  f" ({s.current_source or '-'})  suggested={s.suggested or '-'}")
        if args.apply:
            applied = 0
            for s in suggestions:
                # Never override a family the user picked.
                if s.suggested and s.current_source != "user" and s.current != s.suggested:
                    await bind_resume_family(db, s.resume_id, s.suggested, source="auto")
                    applied += 1
            await db.commit()
            print(f"applied {applied} suggestions")


async def _resumes_set(args) -> None:
    from app.core.database import async_session_factory
    from app.modules.matching.families.resume_binding import bind_resume_family

    async with async_session_factory() as db:
        await bind_resume_family(db, args.resume_id, args.family, source="user")
        await db.commit()
        print(f"{args.resume_id} -> {args.family}")


async def _dataset_create(args) -> None:
    from app.core.database import async_session_factory
    from app.core.llm.gateway import AgentGateway
    from app.modules.matching.evaluation.dataset import DatasetSpec, create_dataset

    spec = DatasetSpec(name=args.name, user_id=args.user, random_n=args.random,
                       filtered_sample=args.filtered_sample, seed=args.seed)
    if not _confirm(args, f"Create dataset {spec}. Classifies role families of dataset jobs "
                          f"with {settings.TITLE_CLASSIFIER_MODEL} where missing."):
        return
    async with async_session_factory() as db:
        dataset = await create_dataset(db, AgentGateway.get(), spec)
        print(f"created {dataset.name}@v{dataset.version} ({dataset.id}): {dataset.item_count} items, "
              f"counts={dataset.config['counts']}, unclassified={len(dataset.config['unclassified_jobs'])}")


async def _run(args) -> None:
    from app.core.database import async_session_factory
    from app.core.llm.gateway import AgentGateway
    from app.modules.matching.evaluation.runner import run_evaluation

    override = ModelOverride(provider=args.provider, model=args.model)
    if not _confirm(args, f"Run {args.dataset} with {override.provider}/{override.model}, "
                          f"repeat={args.repeat} (sample {args.repeat_sample or 'all'}), "
                          f"judged_limit={args.judged_limit or 'all'}, limit={args.limit or 'all'}."):
        return
    run = await run_evaluation(
        async_session_factory, AgentGateway.get(), dataset_ref=args.dataset, model_override=override,
        repeats=args.repeat, concurrency=args.concurrency, baseline_run_id=args.baseline, limit=args.limit,
        judged_limit=args.judged_limit, repeat_sample=args.repeat_sample, sample_seed=args.sample_seed,
    )
    path = _write_report(run.id, run.report_md or "")
    print(f"run {run.id} {run.status}; report: {path}; cost: {run.cost}")


async def _report(args) -> None:
    from app.core.database import async_session_factory
    from app.modules.matching.evaluation.models import MatchEvalRun

    async with async_session_factory() as db:
        run = await db.get(MatchEvalRun, args.run_id)
        if run is None:
            raise SystemExit(f"run {args.run_id} not found")
        print(_write_report(run.id, run.report_md or ""))


async def _compare(args) -> None:
    from app.core.database import async_session_factory
    from app.modules.matching.evaluation.metrics import compare_runs
    from app.modules.matching.evaluation.runner import load_run_rows

    async with async_session_factory() as db:
        diff = compare_runs(await load_run_rows(db, args.run_a), await load_run_rows(db, args.run_b))
    print(f"compared {diff['compared']}, changed {diff['changed']}: {diff['transitions']}")
    for item in diff["items"]:
        print(f"  job {item['job_id']}: {item['from']} -> {item['to']}  {item['title']}")


async def _labels_export(args) -> None:
    from app.core.database import async_session_factory
    from app.modules.matching.labels.csv_io import export_for_labeling

    path = Path(args.out or REPORT_DIR / f"labels_{args.run}.csv")
    async with async_session_factory() as db:
        count = await export_for_labeling(db, args.run, path, limit=args.limit)
    print(f"wrote {count} rows to {path}")


async def _labels_import(args) -> None:
    from app.core.database import async_session_factory
    from app.modules.matching.labels.csv_io import import_labels

    async with async_session_factory() as db:
        result = await import_labels(db, Path(args.file), labeled_by=args.labeled_by, run_id=args.run)
    print(f"imported {result.imported}, blank {result.skipped_blank}")
    for err in result.errors:
        print(f"  {err}")


def _write_report(run_id: str, markdown: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{run_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="matching", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def llm(p):
        p.add_argument("--yes", action="store_true", help="actually call the LLM")
        return p

    fam = sub.add_parser("families").add_subparsers(dest="sub", required=True)
    p = llm(fam.add_parser("classify-titles"))
    p.add_argument("--all", action="store_true", help="every distinct title, not only recent ones")
    p.add_argument("--days", type=int, default=settings.JOB_EXPIRY_DAYS)
    p.set_defaults(func=_families_classify_titles)
    p = llm(fam.add_parser("init"))
    p.add_argument("--days", type=int, default=settings.JOB_EXPIRY_DAYS)
    p.set_defaults(func=_families_init)

    res = sub.add_parser("resumes").add_subparsers(dest="sub", required=True)
    p = res.add_parser("suggest")
    p.add_argument("--user", type=int)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=_resumes_suggest)
    p = res.add_parser("set")
    p.add_argument("resume_id")
    p.add_argument("family")
    p.set_defaults(func=_resumes_set)

    ds = sub.add_parser("dataset").add_subparsers(dest="sub", required=True)
    p = llm(ds.add_parser("create"))
    p.add_argument("--name", default="main")
    p.add_argument("--user", type=int, required=True)
    p.add_argument("--random", type=int, default=300)
    p.add_argument("--filtered-sample", type=int, default=80)
    p.add_argument("--seed", default="jobpilot-v3")
    p.set_defaults(func=_dataset_create)

    p = llm(sub.add_parser("run"))
    p.add_argument("--dataset", required=True)
    p.add_argument("--provider", default=settings.MATCH_LLM_PROVIDER)
    p.add_argument("--model", default=settings.MATCH_JUDGE_MODEL)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--concurrency", type=int, default=settings.MATCH_JUDGE_CONCURRENCY)
    p.add_argument("--baseline")
    p.add_argument("--limit", type=int, help="only the first N dataset items")
    p.add_argument("--judged-limit", type=int, help="only N of the pairs that reach the LLM")
    p.add_argument("--repeat-sample", type=int, help="repeat only N LLM pairs")
    p.add_argument("--sample-seed", default="eval")
    p.set_defaults(func=_run)

    p = sub.add_parser("report")
    p.add_argument("run_id")
    p.set_defaults(func=_report)

    p = sub.add_parser("compare")
    p.add_argument("run_a")
    p.add_argument("run_b")
    p.set_defaults(func=_compare)

    lab = sub.add_parser("labels").add_subparsers(dest="sub", required=True)
    p = lab.add_parser("export")
    p.add_argument("--run", required=True)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--out")
    p.set_defaults(func=_labels_export)
    p = lab.add_parser("import")
    p.add_argument("--file", required=True)
    p.add_argument("--labeled-by", type=int, required=True)
    p.add_argument("--run")
    p.set_defaults(func=_labels_import)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
