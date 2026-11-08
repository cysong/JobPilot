"""Live smoke test of the matching v3 agents through OpenRouter.

Uses synthetic inputs only (no database reads or writes; no ai_calls rows since
no task_id is passed). Costs a few cents.

    uv run python -m scripts.smoke_matching_llm
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import date, datetime, timezone

from app.core.config import settings
from app.core.llm.gateway import AgentGateway
from app.modules.matching.families.classifier import (
    JOB_FAMILY_READER_AGENT,
    TITLE_CLASSIFIER_AGENT,
    TitleToClassify,
    build_jd_read_input,
    build_title_batch_input,
    classifier_override,
    parse_jd_read,
    parse_title_batch,
)
from app.modules.matching.families.registry import get_registry
from app.modules.matching.judge.input_builder import CandidateConditions, CandidateResume, JobInput, SkillLibraryEntry
from app.modules.matching.judge.service import JobContext, UserContext, judge_pair
from app.modules.matching.prefilter import ResumeRef

RESUME = """# Alex Chen — Senior Java Developer
## Work Experience
### Senior Software Engineer, PayCo (2018-03 – 2024-06)
- Built payment reconciliation microservices with Java 17, Spring Boot and Kafka
- Designed PostgreSQL schemas and tuned queries for 20M rows/day
- Deployed services to AWS ECS with Terraform and GitHub Actions
### Software Engineer, ShopNow (2015-01 – 2018-02)
- Developed REST APIs in Java and Spring MVC
## Skills
Java, Spring Boot, Kafka, PostgreSQL, AWS, Docker, Terraform
"""

JOB_HTML_REQUIRES_CITIZEN = """
<p>We are a government agency modernising citizen services.</p>
<p><strong>About the role</strong></p>
<ul>
<li>5+ years building backend services in Java and Spring Boot</li>
<li>Experience with Azure and CI/CD pipelines</li>
<li>Strong SQL skills</li>
</ul>
<p>Applicants must be New Zealand citizens.</p>
"""

PLC_JD = (
    "<p>Join our dairy processing plant team.</p><ul><li>Program and maintain Allen-Bradley PLCs</li>"
    "<li>Support SCADA systems and plant automation upgrades</li></ul>"
)


async def main() -> None:
    gateway = AgentGateway.get()
    registry = get_registry()
    settings.CACHE_ENABLED = False

    print("== title_classifier", settings.TITLE_CLASSIFIER_MODEL)
    items = [TitleToClassify(k, t) for k, t in [
        ("software engineer", "Senior Software Engineer"),
        ("automation engineer", "Automation Engineer"),
        ("service desk analyst", "Service Desk Analyst"),
        ("data science expert", "Data Science Expert"),
        ("devops engineer", "DevOps Engineer"),
    ]]
    ctx: dict = {}
    t0 = time.time()
    out = await gateway.call(TITLE_CLASSIFIER_AGENT, build_title_batch_input(registry, items),
                             context=ctx, model_override=classifier_override())
    for r in parse_title_batch(out, [i.title_key for i in items], registry):
        print(f"  {r.title_key:24} -> {r.status:10} {r.role_family}")
    print(f"  {time.time() - t0:.1f}s usage={ctx.get('usage')}")

    print("== job_family_reader", settings.TITLE_CLASSIFIER_MODEL)
    ctx = {}
    t0 = time.time()
    out = await gateway.call(JOB_FAMILY_READER_AGENT, build_jd_read_input(registry, "Automation Engineer", PLC_JD),
                             context=ctx, model_override=classifier_override())
    reading = parse_jd_read(out, registry)
    print(f"  -> {reading.role_family}: {reading.reason}")
    print(f"  {time.time() - t0:.1f}s usage={ctx.get('usage')}")

    print("== match_judge", settings.MATCH_JUDGE_MODEL)
    now = datetime.now(timezone.utc)
    user = UserContext(
        user_id=0,
        job_locations=(),
        conditions=CandidateConditions(work_rights="work_visa", security_clearance="not_eligible"),
        resumes=(CandidateResume("res_smoke", "Java Developer", "software_dev", RESUME,
                                 ({"duration": ["2018-03", "2024-06"]}, {"duration": ["2015-01", "2018-02"]})),),
        resume_refs=(ResumeRef("res_smoke", "software_dev", now),),
        skills=(SkillLibraryEntry("Azure", "INTERMEDIATE", ("Deployed a side project to Azure App Service",)),),
    )
    from app.modules.matching.text import html_to_text

    job = JobContext(
        job=JobInput(0, "Senior Java Developer", "Wellington", "Full time", now, html_to_text(JOB_HTML_REQUIRES_CITIZEN)),
        location_city="Wellington", is_expired=False, manual_expired=False, expires_at=None, company="Gov",
    )
    t0 = time.time()
    outcome, ctx = await judge_pair(gateway, user=user, job=job, candidate_ids=["res_smoke"], today=date.today())
    print(f"  status={outcome.status} tier={outcome.tier} tech={outcome.tech_level} exp={outcome.experience_level}")
    print(f"  reject={outcome.reject_code}: {outcome.reject_reason} | quote={outcome.reject_quote!r}")
    print(f"  reason: {outcome.tier_reason}")
    print(f"  validation: {json.dumps(outcome.validation)}")
    print(f"  {time.time() - t0:.1f}s usage={ctx.get('usage')}")


if __name__ == "__main__":
    asyncio.run(main())
