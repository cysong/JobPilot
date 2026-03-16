# Development Progress

## Current Status

**Version:** v0.3.0 (Resume Management Module)
**Next Task:** Stage 3 - Application Module

**Last Updated:** 2026-03-16

---

## Work Log

### 2026-03-16 - Frontend Build Failure Fixes

**Completed Tasks:**
- Refactored `frontend/src/api/client.ts` to use typed request helpers instead of returning unwrapped data from an Axios response interceptor.
- Fixed admin React Query hooks to use payload types correctly with TanStack Query v5 placeholder handling.
- Removed frontend TypeScript build blockers caused by unused imports/variables under strict compiler settings.
- Replaced runtime `enum` usage in skill types with `ProficiencyLevel` string-literal typing plus `PROFICIENCY_LEVELS` constants compatible with `erasableSyntaxOnly`.
- Validation:
  - `pnpm exec tsc -b` passed
  - `pnpm run build` passed

### 2026-03-16 - Requirements Alignment for Application Status Flow

**Completed Tasks:**
- Updated `docs/requirements.md` to remove `Resume Screened` from the application status flow.
- Aligned requirements with the current implemented code path:
  - `Pending -> Tailoring -> Ready -> Applied -> Phone Screen -> Interviewing -> Offer -> Rejected`
- Updated the status extension note to keep `Phone Screen` only.

### 2026-03-16 - Backend Runtime Fixes for Job Analysis and Application Resume FK

**Completed Tasks:**
- Fixed `POST /api/v1/jobs/{job_id}/analyze` to use the project task enum instead of Celery's `TaskType`.
- Fixed manual job analysis task submission to use `EntityType.JOB.value`.
- Removed an unused job task import from the analyze endpoint.
- Aligned `applications.source_resume_id` model behavior with business rules:
  - kept the field non-nullable
  - changed FK delete behavior from `SET NULL` to `RESTRICT`
- Added Alembic migration:
  - `20260316_1500_8b2c4d6e9f10_fix_source_resume_fk_behavior.py`

### 2026-03-16 - Backend Static Cleanup for Jobs / Applications / Resumes

**Completed Tasks:**
- Added explicit `TYPE_CHECKING` imports for ORM relationship type hints in backend models.
- Replaced SQLAlchemy boolean comparisons with `.is_(False)` / `.is_(True)` in repository and service queries.
- Removed unused imports in jobs/applications/resumes modules.
- Validation:
  - `ruff check app/modules/jobs app/modules/applications app/modules/resumes` passed

### 2026-03-16 - Effective Job Expiration Filtering Alignment

**Completed Tasks:**
- Upgraded `SeekJob.effective_is_expired` to a SQLAlchemy `hybrid_property` so it can be used consistently in both Python objects and SQL queries.
- Updated backend active-job filtering to honor both crawler expiration and manual expiration flags in:
  - unanalyzed job selection
  - jobs without analysis-task selection
  - similar jobs selection

### 2026-03-16 - Global Manual Job Expiration (Backend + Frontend)

**Completed Tasks:**
- Added global manual expiration fields to `seek_jobs`:
  - `manual_expired`
  - `manual_expired_by`
  - `manual_expired_at`
  - `manual_expired_note`
- Added Alembic migration:
  - `20260316_1030_f4d9a2b6c7e1_add_manual_expired_fields_to_seek_jobs.py`
- Added backend effective-expiration model behavior:
  - `SeekJob.effective_is_expired` combines crawler state + manual state
- Added backend API endpoint for manual global expiration:
  - `PATCH /api/v1/jobs/{job_id}/expiration`
  - supports mark/unmark and optional note
- Updated jobs response schemas to expose manual expiration metadata and effective `is_expired`.
- Updated jobs listing logic to include expired jobs so UI can display expired badges in lists.
- Frontend integration:
  - added job expiration API client and React Query mutation
  - added red `Expired` badge on job cards (list pages)
  - added red `Expired` badge on job detail page
  - added `Mark as Expired` / `Mark as Active` action in job detail page
  - added `Mark as Expired` / `Mark as Active` action in application detail page
  - kept `Apply` link action available (not disabled)
- Validation:
  - backend changed files pass read-only compile validation
  - frontend build still fails due pre-existing TypeScript baseline issues unrelated to this feature

### 2026-03-14 - Admin Jobs Daily Trend Chart (Dashboard Drilldown)

**Completed Tasks:**
- Added backend admin trend API for daily new jobs:
  - endpoint: `GET /api/v1/admin/jobs/daily-trend?days=30`
  - uses system timezone (`settings.APP_TIMEZONE`) only
  - groups by local day and `source`
  - includes one `Total` series
  - fills missing dates with `0`
- Added backend response schemas:
  - `JobsDailyTrendResponse`
  - `JobsDailyTrendSeries`
  - `JobsDailyTrendPoint`
- Added frontend admin chart page:
  - new page: `AdminJobsChartPage`
  - route: `/admin/jobs/chart`
  - title: `Jobs Daily Trend`
  - line chart with source legend + total line
- Added frontend API and hook:
  - `adminApi.getJobsDailyTrend`
  - `useJobsDailyTrend`
- Updated dashboard card behavior:
  - `Jobs` card is now clickable and navigates to `/admin/jobs/chart`
- Validation:
  - backend syntax check passed via `python -m compileall`
  - frontend build currently fails due pre-existing TypeScript issues unrelated to this feature

### 2026-03-13 - Production Deployment Artifacts (Docker + GHCR + Nginx)

**Completed Tasks:**
- Implemented single-image production container build for API/Worker/Beat:
  - added `backend/Dockerfile`
  - added `backend/.dockerignore`
- Added production compose orchestration:
  - added `docker-compose.prod.yml`
  - API/Worker/Beat use the same image with different commands
  - Redis kept internal-only with health checks
- Added VPS deployment script at requested path:
  - added `deploy/deploy-prod.sh`
- Added deployment environment and gateway templates:
  - added `deploy/env/backend.env.example`
  - added `deploy/nginx/jobpilot.conf`
- Added GitHub Actions auto-deploy workflow:
  - added `.github/workflows/deploy.yml`
  - builds and pushes single backend image to GHCR
  - builds frontend and uploads artifact (`frontend-dist`) to GitHub Actions artifact storage
  - runs remote deploy script after merge to `main`
  - remote script pulls frontend artifact from GitHub API by artifact id and publishes to Nginx static directory
- Updated deployment documentation:
  - updated `docs/deployment.md` with actual CORS env key and generated file list
  - added GitHub Secrets checklist used by current deploy workflow
  - added GitHub Variables checklist and wired `VITE_API_BASE_URL` into frontend build workflow

### 2026-03-13 - Hostinger VPS Deployment Plan (GHCR + Unified Nginx)

**Completed Tasks:**
- Added deployment plan document for the agreed production architecture:
  - Hostinger VPS + Docker Manager
  - GHCR image pipeline via GitHub Actions
  - shared Nginx as unified reverse proxy gateway
  - containerized API/Worker/Redis
  - Supabase PostgreSQL as managed database
- Added operational guidance:
  - image tag and rollback policy
  - migration execution order
  - security baseline and monitoring checklist
- Incorporated confirmed production decisions:
  - domain: `app.jobpilot.me` and `api.jobpilot.me`
  - frontend served by Nginx static hosting
  - `Celery Beat` enabled
  - auto deploy on merge to `main`
- Updated image strategy in deployment plan:
  - use one shared image for `api/worker/beat`
  - distinguish runtime roles by startup command only
- Document path:
  - `docs/hostinger_vps_ghcr_deployment_plan.md`

### 2026-03-13 - Jobs: Viewed State + Return Position Restore

**Completed Tasks:**
- Added end-to-end viewed-state support for jobs browsing.
- Added backend viewed data model:
  - new table `user_job_views` with user+job unique constraint
  - fields: `first_viewed_at`, `last_viewed_at`, `view_count`
  - migration: `20260313_1610_5e2c7d9b1a4f_add_user_job_views.py`
- Extended Jobs API:
  - `GET /api/v1/jobs/{job_id}/viewed`
  - `POST /api/v1/jobs/{job_id}/viewed`
  - `GET /api/v1/jobs` now supports `view_status=all|viewed|unviewed`
- Extended jobs response schemas:
  - list/saved/match items now include `is_viewed` and `last_viewed_at`
- Implemented backend viewed filtering and viewed metadata hydration in:
  - job list
  - saved jobs list
  - recommended matches list
- Implemented frontend non-blocking viewed marking:
  - detail page triggers background mark-viewed mutation (no render blocking, no toast interruption)
  - added short dedupe window to avoid excessive repeat calls
- Implemented frontend list position restore across detail navigation:
  - per-context anchor persistence via `sessionStorage`
  - restore and temporary highlight when returning from detail under same context
  - filter/search/sort/view/page context changes reset list to top
- Added viewed UI affordances:
  - `All / Unviewed / Viewed` segmented filter on Jobs list
  - `Viewed` badge and viewed-relative-time on job cards
- Added implementation design doc:
  - `docs/job_browsing_viewed_and_position_plan.md`

### 2026-03-13 - Job Detail Previous/Next Navigation (MVP)

**Completed Tasks:**
- Implemented MVP previous/next navigation in Job detail page based on current list context.
- Added job-order persistence in list page:
  - stores current page job id order by context key (`view + filters + sort + page`) into sessionStorage.
- Added detail-page navigation resolution:
  - resolves `previousJobId` and `nextJobId` from stored context order.
  - keeps query params when navigating between job details.
- Added header controls in Job detail:
  - `Previous` button
  - `Next` button
  - buttons auto-disable at boundaries or when context order not available.
- Scope limited to MVP:
  - current context page only (no cross-page auto-fetch).

### 2026-03-13 - Jobs Company Filter: Debounced Remote Search

**Completed Tasks:**
- Added backend endpoint for company filter remote search:
  - `GET /api/v1/jobs/filters/companies?q=...&limit=...`
- Implemented backend company search logic in jobs service:
  - searches both `company_name` and `advertiser_name`
  - filters out null/empty values and expired jobs
  - merges and deduplicates results (case-insensitive) before returning
  - supports keyword fuzzy match with `ILIKE`
- Updated frontend jobs API and hooks:
  - added `jobsApi.searchCompanies`
  - added `useCompanyFilterOptions` (React Query)
- Added new frontend dropdown component:
  - `CompanyFilterDropdown` with 300ms debounce and remote search
  - preserves selected companies while searching
- Replaced static company options dropdown in Job Listing page with the new remote-search dropdown.

### 2026-03-12 - Admin Task List UX: Debounced Retry Refresh + Auto Exit Animation

**Completed Tasks:**
- Implemented debounced refresh after manual retry in task monitor page:
  - removed immediate query invalidation from retry mutation hook.
  - added page-level delayed refresh (1.2s) that coalesces multiple retry successes into a single `tasks` + `statistics` refetch.
  - ensured pending timer cleanup on unmount and when user clicks manual `Refresh`.
- Added automatic list enter/exit animation for task cards:
  - installed `@formkit/auto-animate`.
  - attached animation container to task list rendering block so removed task rows now animate out instead of disappearing instantly.
- Preserved existing retry failure behavior (toast + no forced refresh changes).

### 2026-03-12 - Admin Task Retry Load Reduction (Fast Path + Targeted Broker Check)

**Completed Tasks:**
- Optimized manual retry path in `TaskService.retry_task` to avoid unnecessary broker inspection for failed anchors.
- Added fast-path behavior in retry eligibility check:
  - `FAILED` anchor tasks are immediately eligible without Celery queue snapshot checks.
- Replaced full broker task-id set construction with targeted single-ID presence check:
  - new helper checks only the anchor task `celery_task_id` when needed.
  - broker inspection is now triggered only for stale `Pending` / `Running` anchors that have a `celery_task_id`.
- Removed now-unused full-snapshot helper to keep retry code path lean and maintainable.
- Performed syntax validation for updated backend service module.

### 2026-03-12 - Shared Pagination Fix (Duplicate Last Page Numbers)

**Completed Tasks:**
- Investigated admin task page pagination issue where last-page numbers were repeated (e.g., multiple `10` with total `198` records).
- Confirmed root cause in shared UI pagination algorithm (`frontend/src/components/ui/pagination.tsx`) rather than backend total/page calculation.
- Refactored page window generation to a bounded sliding-window strategy:
  - stable `startPage` / `endPage` clamp
  - strictly increasing, unique `pageNumbers` array
  - removed duplicated page keys during near-end rendering
- Kept existing pagination interactions unchanged:
  - first/prev/next/last buttons
  - trailing ellipsis behavior
- Impact scope verified:
  - admin tasks list pagination
  - jobs listing pagination
  - applications listing pagination
  (all reuse the same shared `Pagination` component)

### 2026-03-12 - PDF Export Filename Rule Unification (Resume + Cover Letter)

**Completed Tasks:**
- Fixed application PDF filename sanitization to remove symbol-only fragments when converting to underscore format.
- Unified backend naming behavior for:
  - `POST /api/v1/applications/{application_id}/resume/export`
  - `POST /api/v1/applications/{application_id}/cover-letter/export`
- Updated backend sanitizer in:
  - `backend/app/modules/applications/service.py`
  - `backend/app/modules/resumes/export/service.py`
- Added shared frontend filename utility:
  - `frontend/src/utils/pdfFilename.ts`
- Replaced duplicated frontend filename logic in:
  - `frontend/src/features/applications/ApplicationDetailPage.tsx`
  - `frontend/src/features/applications/TailoredResumeEditPage.tsx`
  - `frontend/src/features/applications/CoverLetterEditPage.tsx`
- Result example:
  - Input job title: `Spaceplane - HITL Engineer`
  - Output: `Anson_Chen_Resume_Spaceplane_HITL_Engineer.pdf` (dropped symbol-only `-` token)

### 2026-03-12 - Jobs: Saved (Watchlist) Feature

**Completed Tasks:**
- Added backend saved-jobs data model `user_saved_jobs` (user + job unique pair).
- Added Alembic migration:
  - `20260312_2300_7f4d2c9ab1e0_add_user_saved_jobs.py`
- Added Jobs API endpoints:
  - `GET /api/v1/jobs/saved`
  - `GET /api/v1/jobs/{job_id}/saved`
  - `POST /api/v1/jobs/{job_id}/saved`
  - `DELETE /api/v1/jobs/{job_id}/saved`
- Added frontend API/types/hooks for saved jobs.
- Updated Job detail page:
  - Added star save toggle button (`Save` / `Saved`)
  - Filled gold star visual for saved state
- Updated Job listing page:
  - Added `Saved` tab next to `Recommended` and `All Jobs`
  - Renders saved jobs sorted by saved time (newest first, from backend)
- Updated Job card time copy for saved context:
  - `saved x days ago`
  - Uses the same `formatDistanceToNow(..., { addSuffix: true })` logic as `listed_at`.
- Per requirement, did not add expired-job handling in saved flow.

### 2026-03-12 - Application Timestamps: applied_at and offered_at

**Completed Tasks:**
- Added `applications.applied_at` and `applications.offered_at` model fields (nullable, indexed).
- Added Alembic migration to create the two columns and indexes:
  - `20260312_1730_c31f8b6f2a90_add_applied_offered_at.py`
- Updated application API response schema to include:
  - `applied_at`
  - `offered_at`
- Updated status transition service logic:
  - first transition to `Applied` sets `applied_at` (write-once)
  - first transition to `Offer` sets `offered_at` (write-once)
- No historical backfill added per requirement.
- No frontend display/statistics changes added per requirement.

### 2026-03-12 - Application Detail: Apply Button + Status Transition Actions

**Completed Tasks:**
- Added backend API for manual application status update:
  - `PATCH /api/v1/applications/{application_id}/status`
  - payload: `status`, optional `note`
- Implemented guarded status transition rules in service layer:
  - `Ready -> Applied`
  - `Applied -> PhoneScreen | Rejected`
  - `PhoneScreen -> Interviewing | Rejected`
  - `Interviewing -> Offer | Rejected`
  - `Failed -> Pending`
- Added status change history append into `tailoring_progress.status_history`.
- Updated async workflow to set status to `Tailoring` when resume tailoring starts.
- Added frontend API/hook support for status updates.
- Updated Application detail page actions:
  - Added `Apply` button linking to job original posting (`job.share_link`)
  - Added dynamic status transition action buttons based on current status
  - `Retry Generation` is now limited to `Failed` status.

### 2026-03-12 - Job Detail Similar Jobs: Hide Reason Tags + Company Name Consistency

**Completed Tasks:**
- Temporarily commented out recommendation reason badges (`Same company` / `Same classification`) in similar job cards on the job detail page.
- Unified company display logic in job detail page via shared helper:
  - Current job header/company section and similar job cards now use the same fallback order:
    - `advertiser_name` -> `company_name` -> `Unknown company`
- Removed now-unused inline reason helper logic from page runtime path.

### 2026-03-12 - Job Detail: Similar Jobs Module (Phase 1)

**Completed Tasks:**
- Connected `useSimilarJobs(jobId, 5)` to the job detail page sidebar.
- Replaced previous placeholder with a production-ready `Similar Jobs` card section.
- Added loading skeleton state for similar jobs request.
- Added empty state copy: `No similar jobs found.`
- Rendered similar job items with key fields:
  - title (navigable link)
  - company
  - location
  - relative posted time
- Added explainability tags for recommendation reasons:
  - `Same company`
  - `Same classification`
- Preserved listing query params when navigating from detail page to a similar job detail.

### 2026-03-11 - Applications Listing: Search + Status Filter + Pagination Params

**Completed Tasks:**
- Extended `GET /api/v1/applications` to support query params:
  - `keyword`
  - `status`
  - `page`
  - `page_size`
- Added backend filtering in application repository:
  - Keyword search on job title/company fields
  - Exact status filter
  - Kept pagination + created-at descending sort
- Updated frontend applications API/hook typing to use filter object:
  - `ApplicationListRequest` with `keyword/status/page/page_size`
- Refactored Applications listing page to URL-param-driven behavior:
  - Search input bound to `keyword`
  - Status dropdown bound to `status`
  - Pagination bound to `page`
  - `page_size` preserved in URL/query
  - Reset/Clear filters UX
- Improved empty-state copy for filtered results ("no matches" vs "no applications yet").

### 2026-03-11 - Applications Listing UX: Keep Filters Stable During Refetch

**Completed Tasks:**
- Updated applications query hook to keep previous page data during filter/pagination refetch (`placeholderData: keepPreviousData`).
- Refactored applications listing page loading behavior so search/filter controls remain mounted while results refresh.
- Added lightweight in-page refetch indicator (`Updating results...`) instead of full-page loading replacement.

### 2026-03-11 - Application Detail Header Alignment Fix

**Completed Tasks:**
- Removed negative left margin on the header back button in application detail page (`-ml-2` -> removed) to align header operation content with the job card visual width.

### 2026-03-11 - Tailoring Level Enum Validation + Configurable Retry Flow

**Completed Tasks:**
- Added strict tailoring level enum support (`light`, `moderate`, `deep`) in application domain schemas/models.
- Added DB migration with `applications.tailoring_level` check constraint and invalid historical value normalization.
- Extended retry API to accept optional payload:
  - `resume_template_id` (switch source resume template on retry)
  - `tailoring_level` (override tailoring level on retry)
- Updated retry backend orchestration to rerun only:
  - `resume_tailoring`
  - `cover_letter_generation`
- Added frontend tailoring level selection in application creation dialog (default `light`).
- Added application detail retry dialog allowing users to reselect template and tailoring level before retry.
- Fixed retry document-chain handling:
  - On retry, backend now creates a new working document from selected template.
  - New working document links to previous application resume document as `parent_id`.
  - `root_id` is preserved from previous chain and `application.resume_document_id` is updated to the new working document before rerunning tasks.

### 2026-03-11 - Cover Letter Pipeline Simplification (Writer-Only)

**Completed Tasks:**
- Removed reviewer loop from cover letter generation; pipeline now uses `cover_letter_writer` only.
- Removed `tailoring_level` from cover-letter task prompt input (resume tailoring still keeps `tailoring_level`).
- Updated cover letter schema to return full document text directly (`content`) with `word_count`.
- Updated `cover_letter_writer` prompt to produce complete markdown/plain text and perform internal self-check.
- Added per-agent override `max_turns: 2` for `cover_letter_writer`.
- Optimized writer prompt payload with compact JSON and empty-field pruning.

### 2026-03-11 - Resume Tailor Prompt Optimization for ATS + Interview Shortlist

**Completed Tasks:**
- Rewrote `resume_tailor` agent instructions to optimize for both ATS pass likelihood and recruiter interview shortlist outcomes.
- Strengthened hard constraints to preserve immutable facts and structure while allowing wording-level refinement in project/work bullets.
- Added explicit JD-resume overlap strategy and prioritization order:
  - Summary -> Skills -> top experience bullets.
- Elevated Summary requirements with concrete rules:
  - role/seniority positioning,
  - top JD technical strengths with evidence,
  - JD-relevant soft trait with evidence.
- Added final self-check rules to reduce unsupported claims and factual drift.

### 2026-03-11 - Resume Tailor Prompt Compaction & Per-Agent max_turns Override

**Completed Tasks:**
- Optimized resume tailoring prompt payload construction:
  - `job_analysis` now uses compact JSON (no indentation).
  - `user_skills` now uses compact JSON (no indentation).
  - Added empty-field pruning for prompt payloads (removes `None`, empty strings, empty lists/dicts).
- Added per-agent `max_turns` override support in LLM agent loading/runtime:
  - New optional YAML field: `max_turns`.
  - Default behavior remains global `LLM_AGENT_MAX_TURNS`.
  - Agent-level `max_turns` now overrides global default when configured.
- Configured `resume_tailor` with `max_turns: 3` for single-round, no-tool tailoring behavior.

### 2026-03-10 - Celery Task State Consistency & Failure Visibility Fix

**Completed Tasks:**
- Fixed async hook DB updates in `DBTrackingTask` to avoid `This event loop is already running` by executing hook coroutines safely even when worker loop is active.
- Improved task state transitions:
  - `mark_running` now clears stale completion/error fields.
  - `mark_success` now clears stale error fields.
- Added explicit failure progress updates for application pipeline tasks:
  - `resume_tailoring_task` and `cover_letter_generation_task` now set progress step to `failed` on exception.
- Decoupled AI call metrics persistence from task transaction rollback:
  - `AgentGateway._record_ai_call` now writes via an independent DB session/transaction.

### 2026-03-10 - Unified Backend Text Log Persistence (API + Celery)

**Completed Tasks:**
- Added unified logging initializer with rotating file handlers and plain-text formatter:
  - `backend/app/core/logging_config.py`
- Added configurable logging settings in backend config:
  - `LOG_LEVEL`, `LOG_DIR`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`
- Wired logging initialization into process entry points:
  - `backend/app/main.py` (API -> `logs/api.log`)
  - `backend/run_celery_worker.py` (worker -> `logs/celery-worker.log`)
  - `backend/run_celery_beat.py` (beat -> `logs/celery-beat.log`)
- Ensured Celery keeps application logging configuration:
  - `worker_hijack_root_logger=False` in `backend/app/core/celery_app.py`
- Updated environment template with logging variables:
  - `backend/.env.example`

**Notes:**
- `ai-calls.log` was intentionally not added; AI logs are written with task logs.
- Output format is text-only (no JSON logging).
- API and task logs use different text formats to avoid noisy placeholder fields in API logs.



### 2026-03-10 - Job Source Expansion (Seek + LinkedIn)

**Completed Tasks:**
- Added `source` field support across job backend model/schema/service/router for list/detail/filter APIs.
- Added `sources` filter support in `GET /api/v1/jobs` and filter options in `GET /api/v1/jobs/filters`.
- Updated frontend job types and API query builder to include `source/sources`.
- Added Source filter in job listing page (URL state + filter count + dropdown integration).
- Updated job detail CTA text from platform-specific wording to generic `Open Original Posting`.
- Added source badges to Job card and Job detail header.
- Improved UI fallback behavior: hide classification/sub-classification display when corresponding fields are empty.

### 2026-03-10 - LLM Upgrade (GPT-5 / GPT-5-mini) for Resume & Cover Letter Quality

**Completed Tasks:**
- Upgraded agent models from GPT-4.1 family to GPT-5 family:
  - `resume_tailor` -> `gpt-5`
  - `cover_letter_writer` -> `gpt-5`
  - `reviewer` -> `gpt-5-mini`
  - `resume_analyzer`, `job_analyzer`, `match_analyzer`, `universal_translator` -> `gpt-5-mini`
- Optimized `resume_tailor` prompt for higher-fidelity tailoring with explicit hard constraints and self-check flow:
  - preserve immutable facts/structure
  - strengthen JD alignment without hallucination
  - evidence-grounded `notes` output guidance
- Optimized `cover_letter_writer` prompt with quality rubric + self-check:
  - stronger evidence density and role relevance
  - stricter anti-template / anti-generic style constraints
  - explicit JSON-only output rules for `CoverLetterDraft`
- Optimized `reviewer` prompt with deterministic gating rules and actionable issue format:
  - score thresholds for `needs_revision`
  - concrete fix-oriented issue requirements
- Updated backend model pricing config to include `gpt-5` and `gpt-5-mini` so AI cost tracking remains accurate.

### 2026-03-10 - LLM Reasoning Control Support (Agent YAML + Loader)

**Completed Tasks:**
- Refactored agent configuration format to unified nested `model_settings` in all YAML agents.
- Extended `AgentLoader` to read and pass `model_settings` directly into `ModelSettings(...)`.
- Intentionally removed old top-level tuning compatibility (`temperature/max_tokens/top_p` on root level).
- Added reasoning and verbosity controls per agent:
  - High reasoning: `resume_tailor`
  - Medium reasoning: `cover_letter_writer`
  - Low reasoning: `reviewer`, analyzers, translator
- Standardized runtime behavior so GPT-5/GPT-5-mini can use reasoning-depth controls from config.

### 2026-03-10 - Resume Deletion Task Submission Bug Fix

**Completed Tasks:**
- Fixed `delete_resume` formal-resume branch to call `TaskService.submit_task(...)` with the correct signature.
- Removed incorrect `spec=TaskSubmissionSpec(...)` usage that could raise runtime `TypeError` and block skill aggregation task dispatch.
- Verified no remaining `submit_task(spec=...)` usage in backend modules.


### 2026-01-08 - Application PDF Export for Tailored Resume & Cover Letter

**Completed Tasks:**
- Added application-level PDF export endpoints for tailored resume and cover letter.
- Implemented safe, job-aware filenames for application document downloads.
- Added cover letter PDF template + CSS and wired frontend download buttons for application documents.


### 2026-01-06 - Document Draft Restore Prompt Fix

**Completed Tasks:**
- Adjusted DocumentEditPage draft restore prompt to only show when local draft differs from server content, reducing false positives after title edits.
- Split title saving (onBlur) from content saving (Save) in DocumentEditPage, and limited drafts to content only.

### 2025-12-18 - User Skills Management System Implemented

**Completed Tasks:**

**Backend Implementation:**
- ✅ **Data Models**: Created dual-table architecture for skill management
  - `ResumeSkill`: Stores raw skills extracted from resume analysis (UUID primary key)
  - `UserSkill`: Stores aggregated and deduplicated user skills (UUID primary key)
  - Added `ProficiencyLevel` enum (beginner, intermediate, advanced, expert)
  - Updated User model to include skills relationship
- ✅ **Task System**: Implemented `SKILL_AGGREGATION` task type based on `DBTrackingTask`
  - `aggregate_user_skills_task`: Async Celery task for skill aggregation
  - Automatically triggered after resume analysis (for formal resumes only)
  - Automatically triggered when formal resumes are deleted
- ✅ **Service Layer**: Created comprehensive skill management service ([app/modules/users/service.py](../backend/app/modules/users/service.py))
  - `aggregate_user_skills()`: Deduplication and merging logic with priority rules
  - `get_user_skills()`: Retrieve all user skills with sorting
  - `create_user_skill()`: Manually add skills
  - `update_user_skill()`: Update proficiency (marks as manual)
  - `delete_user_skill()`: Delete skills
  - `save_resume_skills()`: Save skills from resume analysis
- ✅ **API Endpoints**: Created skill management REST API ([app/modules/users/router.py](../backend/app/modules/users/router.py))
  - `GET /api/v1/skills` - List all user skills with statistics
  - `POST /api/v1/skills` - Manually add a skill
  - `PUT /api/v1/skills/{skill_id}` - Update skill proficiency
  - `DELETE /api/v1/skills/{skill_id}` - Delete a skill
  - `POST /api/v1/skills/sync` - Manually trigger skill aggregation
- ✅ **Workflow Integration**:
  - Resume analysis flow: Extracts skills → saves to resume_skills → triggers aggregation
  - Resume deletion flow: Soft delete → triggers skill re-aggregation (for formal resumes)
- ✅ **Dependency Injection**: Updated router to use `Annotated` format with `get_current_user`

**Frontend Implementation:**
- ✅ Created TypeScript types ([frontend/src/types/skill.ts](../frontend/src/types/skill.ts))
  - ProficiencyLevel enum
  - UserSkill, UserSkillCreate, UserSkillUpdate interfaces
  - UserSkillListResponse, SkillSyncResponse
- ✅ Built Skills API client ([frontend/src/api/skills.ts](../frontend/src/api/skills.ts))
  - getSkills(), createSkill(), updateSkill(), deleteSkill(), syncSkills()
- ✅ Implemented React Query hooks ([frontend/src/features/skills/hooks/useSkills.ts](../frontend/src/features/skills/hooks/useSkills.ts))
  - useSkills() for data fetching
  - useSkillMutations() for CRUD operations
- ✅ Built comprehensive UI components:
  - `SkillsManagement`: Main management component with statistics and skill lists
  - `AddSkillDialog`: Modal for manually adding skills
  - `EditSkillDialog`: Modal for updating skill proficiency
- ✅ Created Skills page ([frontend/src/features/skills/SkillsPage.tsx](../frontend/src/features/skills/SkillsPage.tsx))
- ✅ **Navigation Integration**:
  - Added `/skills` route to App.tsx
  - Added "Skills" menu item to desktop navigation (Navigation.tsx)
  - Added "Skills" menu item to mobile navigation (MobileNav.tsx) with Award icon

**Key Features Implemented:**
- Dual-table design: resume_skills (raw) + user_skills (aggregated)
- Automatic skill extraction from resume analysis
- Manual skill management (add/edit/delete)
- Skill deduplication across multiple resumes
- Priority-based merging: manual skills > high proficiency skills
- Cascade deletion: resume_skills auto-deleted when resume is deleted
- Real-time skill aggregation via Celery tasks
- Comprehensive UI with statistics and categorization (manual vs auto-extracted)
- Mobile-responsive design using shadcn/ui components

**Database Migration:**
- Migration file created: `20251218_2247_b6a3d58b1436_refactor_user_skills.py`
- User needs to execute: `uv run alembic upgrade head`

**Pending:**
- Execute database migration manually
- Test skill extraction from resume analysis
- Test skill aggregation after resume deletion
- Verify UI functionality in browser

---

### 2025-12-17 - Admin Dashboard Backend Foundations
**Completed Tasks:**
- Created admin module scaffolding (`backend/app/modules/admin/{__init__,dependencies,schemas,service,router}.py`) with router-level `require_admin`.
- Implemented worker监控、Dashboard统计、任务列表/详情/统计、单个/批量重试等接口并注册到 API v1。
- Worker监控改为直接使用 Celery inspect 聚合 active/queued/running 状态与 worker 列表。
- 补全 admin Pydantic schemas（DashboardStats、WorkerMonitorResponse、TaskList/Detail/Retry/Statistics）。

**Pending:**
- 为 admin 接口补充权限与集成测试；前端 hooks/UI 对接 `/admin/*`。
- 校验 Celery stats 里的心跳字段可用性，必要时调整心跳/队列指标来源。

### 2025-12-15 - Unified API Response Format (Backend & Frontend)
**Completed Tasks:**

**Backend Implementation:**
- Added unified response code/model/route: `backend/app/core/response_codes.py`, `response.py`, `custom_route.py`; updated exceptions to carry `response_code`.
- Applied global handlers and custom route: `backend/app/main.py`, `backend/app/api/v1/router.py`.
- Refactored auth/jobs/resumes/applications routers and services to use unified exceptions and auto-wrapping; async task endpoints (job analysis) return `{code,message,data}`; kept file download passthrough.
- Updated auth security dependency to emit unified errors.

**Frontend Implementation:**
- Added unified types and ApiError: `frontend/src/types/api.ts`.
- Axios client now unwraps `{code,message,data}`, handles 401/419/403/1001/1002, and passes through binary downloads.
- Adapted API clients (auth/jobs/resumes/applications) to use unwrapped payloads.
- Updated UI error handling to use ApiError in auth screens and applications hooks.

**Pending:**
- Run frontend build/lint (`pnpm build`/`pnpm lint`) and backend smoke tests (health, 404, pagination, business code paths).

### 2025-12-15 - Task Execution Refactor (Celery + Single Task Table)
**Completed Tasks:**

- **DB schema**: Added `entity_type/entity_id/user_id` to `task_executions`, backfilled from workflows with mapping (job_analysis→job, resume_analysis→resume, cover_letter_generation→application), dropped `workflow_executions` table, new indexes; Alembic script `20251215_1300_switch_to_single_task_table.py` (not executed).
- **Task bases**: Introduced `AsyncBaseTask` (async + self.db) and `DBTrackingTask` (status/elapsed/retry_count tracking) replacing `_run_sync`/decorators.
- **Service layer**: Added `TaskService.submit_task` and `submit_sequential_tasks` (Celery chain) with `TaskSubmissionSpec`; `WorkflowService` deprecated.
- **Task migrations**: Jobs/resumes/matching/applications Celery tasks now use new bases and drop `get_db` loops; retry count persisted via `request.retries`; matching puller/outbox consumer updated.
- **Resume flows**: `_trigger_analysis_if_needed` & `trigger_resume_analysis` submit sequential `resume_analysis` → `match_user_jobs` via chain.
- **Legacy cleanup**: Removed workflow decorator/template code; `AICall` detached from workflow FK; model imports aligned.

**Pending:**
- Run Alembic upgrade manually.
- Restart Celery workers/beat to load new task bases and chains.
- Smoke test chained tasks (resume analysis → match) and tracked task state updates.

### 2025-12-07 - Job Analysis 拆分与缓存实现

**Completed Tasks:**

**Backend Implementation:**
- ✅ **数据模型**: 创建 `job_analyses` 表，存储 AI 分析结果（10+ 字段：skills, certifications, tech_stack, responsibilities, seniority, education, soft_skills, culture, hiring_priorities）
- ✅ **Repository 层**: 新增 `JobRepository` 和 `JobAnalysisRepository`，统一数据库查询逻辑
  - `get_by_id()`, `get_unanalyzed_jobs()` - Job 查询
  - `get_by_job_id()`, `create()`, `delete_by_job_id()` - Analysis CRUD
- ✅ **Agent 配置优化**: 更新 `job_analyzer.yaml`，扩展 prompt 指导（一致性、去广告、字段提取规则），提升分析质量
- ✅ **Celery 任务**:
  - `analyze_job_async(job_id)` - 异步分析单个 Job，成功后存入 `job_analyses` 表
  - `poll_unanalyzed_jobs()` - 定时轮询未分析 Job，批量触发分析（每 5 分钟，每次 3 个 job）
- ✅ **Celery Beat 调度**: 配置定时任务，自动分析新入库 Job
- ✅ **重构 Cover Letter 流程**:
  - 移除 `_analyze_job()` 函数（原每次重复调用 Agent）
  - 新增 `_get_job_analysis()` 函数（优先读缓存，缓存缺失时触发异步分析并 Retry）
  - 大幅降低 AI 成本和生成延迟
- ✅ **配置项**: 新增 `MAX_JOBS_PER_POLL=3` 和 `JOB_ANALYSIS_VERSION=v1.0.0`
- ✅ **API 端点** (用于测试):
  - `GET /api/v1/jobs/{job_id}/analysis` - 查询缓存的分析结果
  - `POST /api/v1/jobs/{job_id}/analyze` - 手动触发分析
  - `DELETE /api/v1/jobs/{job_id}/analysis` - 删除缓存（用于重新分析）
- ✅ **Alembic Migration**: `20251207_1159_b66996638246_add_job_analyses_table.py`

**架构改进:**
- **解耦设计**: Job Analysis 独立于 Cover Letter 生成流程
- **缓存机制**: 同一 Job 分析结果复用，避免重复 AI 调用
- **异步处理**: Polling + Celery 自动化分析，无需手动触发
- **扩展性**: 通过 `analysis_version` 支持未来 Schema 升级

**架构优化 (2025-12-07 下午):**
- ✅ **Schema 版本自动化**: 所有 Agent Schema 定义 `__version__` 类属性（单一真实来源）
- ✅ **自动版本检测**: Task 层自动从 Schema 读取版本，无需维护配置文件
- ✅ **自动版本升级**: Service 层检测版本不匹配时自动触发重新分析（懒加载升级）
- ✅ **文档完善**: 创建 [agent-schema-versioning.md](agent-schema-versioning.md) 版本管理指南

**待测试:**
- [ ] 手动触发 Job 分析（`POST /jobs/{id}/analyze`）
- [ ] 验证分析结果存储正确（`GET /jobs/{id}/analysis`）
- [ ] Cover Letter 生成使用缓存（检查 AI 调用次数）
- [ ] Celery Beat 自动轮询（启动 worker + beat）

---

### 2025-11-26 - LLM Gateway 与 Cover Letter Agent 编排

**Completed Tasks:**

**Backend Implementation:**
- 引入 LLM Gateway 基础设施：新增 `backend/app/core/llm/`（config/loader/gateway/types）与 YAML Agent 配置（`backend/agents/config/*.yaml`），统一 Agent 定义与成本计算。
- 定义结构化输出模型与注册表 `backend/agent_configs/schemas.py`，支持 AnalyzedJob/AnalyzedResume/CoverLetterDraft/ReviewResult。
- 重构封面信任务：`backend/app/modules/applications/llm/cover_letter_task.py` 使用 AgentGateway 调用 `job_analyzer`、`resume_analyzer`、`cover_letter_writer`、`reviewer`，支持最多 2 次迭代与评分阈值 8.0，保持文档生成、Workflow/Task 状态更新、AI 调用记录与 Outbox 事件。
- Celery 入口 `applications.generate_cover_letter` 迁移为调用新任务模块，Service 层不再承担生成逻辑。


### 2025-11-24 - Application Workflow Backend Implemented

**Completed Tasks:**

**Backend Implementation:**
- Added application workflow scaffolding (Celery + workflow/task/outbox/ai_call models) and application API routes for create/get/retry (backend/app/modules/applications/*, backend/app/api/v1/router.py).
- Implemented cover-letter generation task via DeepSeek (OpenRouter) with workflow/task status updates, AI usage logging, and outbox events; added Celery app config (backend/app/core/celery_app.py).
- Updated application schema: status default Pending, source resume + resume/cover documents, soft delete fields, unique (user_id, job_id), last_error, removed workflow_id FK; aligned Alembic migration and architecture doc.
- Added OpenRouter configuration fields; documented backend plan in docs/application-plan.md.

**Pending:**
- Run Alembic migrations to apply updated application/workflow tables.
- Start Celery worker alongside API after setting AI credentials (OPENROUTER_API_KEY or alternatives).

### 2025-11-24 - Resume Management Frontend Completed

**Completed Tasks:**

**Frontend Implementation:**
- ✅ Created TypeScript types (`src/types/resume.ts`) and API client (`src/api/resumes.ts`)
- ✅ Implemented React Query hooks (`src/features/resumes/hooks/useResumes.ts`)
- ✅ Built Resume Management UI:
  - `ResumeListingPage`: Grid view of resumes with create/delete actions
  - `ResumeEditPage`: Split-pane Markdown editor with real-time preview
  - `ResumeCard`: Display resume status (Draft/Formal) and metadata
- ✅ Integrated `react-markdown` for resume preview
- ✅ Implemented PDF export trigger (downloads blob from backend)
- ✅ Configured routes: `/resumes`, `/resumes/new`, `/resumes/:id`

**Refactoring & Optimization:**
- ✅ **Directory Structure**: Standardized `src/features/resumes` (removed `pages` subdirectory)
- ✅ **Configuration**: Fixed `shadcn/ui` alias issue (moved files from `@` to `src`)
- ✅ **Landing Page**: Updated content (removed "AI Cover Letter" badge and trial text)

**Key Features Implemented:**
- Full CRUD for resumes (Create, Read, Update, Delete)
- Draft vs. Formal resume workflow
- Markdown-based resume editing
- Real-time preview
- PDF Export integration

---

### 2025-11-24 - Project Layout & Access Control Completed

**Completed Tasks:**

**Frontend Implementation:**
- ✅ Implemented **Public Layout** (Landing Page) with responsive design
- ✅ Implemented **Main Layout** (Authenticated) with Top Navigation and User Menu
- ✅ Built `Navigation` component with responsive mobile drawer (`Sheet`)
- ✅ Built `UserNav` component with Avatar dropdown and Logout functionality
- ✅ Created `PlaceholderPage` for unimplemented features (Dashboard, Applications, Resumes)
- ✅ Configured `App.tsx` with Public and Protected routes
- ✅ Adapted `JobListingPage` to the new layout structure

**Refactoring & Optimization:**
- ✅ **Directory Structure**: Merged `src/layouts` into `src/components/layout` for a flatter structure
- ✅ **Utility Functions**: Standardized `cn` utility in `src/utils/cn.ts`
- ✅ **Configuration**: Added `components.json` for shadcn/ui and configured path aliases (`@/utils/cn`)
- ✅ **Documentation**: Updated `docs/frontend_development_guide.md` with new structure and standards

**Key Features Implemented:**
- Unified navigation experience for authenticated users
- Modern, responsive Landing Page for public visitors
- Secure access control (redirects to login if unauthenticated)
- Mobile-friendly navigation menu

---

### 2025-11-24 - Document Export System Implemented

**Completed Tasks:**

**Backend Implementation:**
- ✅ Refactored PDF export system to support multiple document types (方案 3: 混合方案)
- ✅ Created **DocumentExportService** - Universal export service ([app/modules/resumes/export/service.py](app/modules/resumes/export/service.py))
  - `export_to_pdf()`: Generic export method for all document types
  - `get_available_document_types()`: Auto-discover document types
  - `get_available_templates(document_type)`: Get templates per type
- ✅ Refactored **PDFGenerator** to support `document_type` parameter ([app/modules/resumes/export/generator.py](app/modules/resumes/export/generator.py))
  - Template path: `templates/{document_type}/{template_name}.html`
  - CSS path: `css/{document_type}/base.css` + `css/{document_type}/{template}.css`
  - Added `get_available_document_types()` method
  - Updated `get_available_templates(document_type)` method
  - Updated `validate_template(document_type, template_name)` method
- ✅ Reorganized template directory structure:
  - `templates/resume/` - Resume templates (modern/classic/minimal)
  - `templates/cover_letter/` - Cover letter templates (to be created)
- ✅ Reorganized CSS directory structure:
  - `css/resume/` - Resume styles (base.css + template-specific)
  - `css/cover_letter/` - Cover letter styles (to be created)
- ✅ Updated **ResumeService** to use DocumentExportService ([app/modules/resumes/service.py](app/modules/resumes/service.py:394-453))
  - Calls `DocumentExportService.export_to_pdf(document_type="resume")`
- ✅ Updated Resume API endpoints ([app/modules/resumes/router.py](app/modules/resumes/router.py))
  - Updated `/resumes/templates` to call `DocumentExportService.get_available_templates("resume")`
- ✅ Updated configuration ([app/core/config.py](app/core/config.py:55))
  - Renamed `RESUME_EXPORT_DEFAULT_TEMPLATE` → `EXPORT_DEFAULT_TEMPLATE`
  - Now applies to all document types

**Documentation:**
- ✅ Updated [docs/resume-export.md](docs/resume-export.md) to reflect new architecture


**Key Features Implemented:**
- Multi-document type support (resume, cover_letter, etc.)
- Template and CSS isolation by document type
- Auto-discovery of document types and templates
- Easy extension: just add new `templates/{type}/` and `css/{type}/` directories
- Backward compatible: existing resume export API unchanged


---

### 2025-11-24 - Resume Management Module Backend Completed

**Completed Tasks:**

**Backend Implementation:**
- ✅ Created Document model with chained version support ([app/modules/resumes/models.py](app/modules/resumes/models.py))
  - Support for Markdown/HTML/PlainText formats
  - Version chain via root_id and parent_id
  - SHA-256 content hashing for deduplication
  - JSON metadata field for extensibility
- ✅ Created Resume model with draft/formal workflow ([app/modules/resumes/models.py](app/modules/resumes/models.py))
  - Soft delete support (is_deleted, deleted_at)
  - One-to-one relationship with Document
  - Draft/formal status tracking
- ✅ Implemented Pydantic schemas ([app/modules/resumes/schemas.py](app/modules/resumes/schemas.py))
  - DocumentBase, DocumentVersion
  - ResumeCreate, ResumeUpdate, ResumeTitleUpdate
  - ResumeResponse, ResumeListItem, ResumeListResponse
  - FormalResumeLimit
- ✅ Built ResumeService with 9 core methods ([app/modules/resumes/service.py](app/modules/resumes/service.py))
  - create_resume(): Creates document + resume with version tracking
  - get_resumes(): Paginated list with draft/formal filtering
  - get_resume_by_id(): Retrieve single resume with document content
  - update_resume(): Creates new document version, updates content
  - update_resume_title(): Title-only update
  - finalize_resume(): Convert draft to formal with quota check (limit: 3)
  - delete_resume(): Soft delete
  - check_formal_resume_limit(): Quota check
  - get_resume_versions(): Version history
- ✅ Created Resume API endpoints ([app/modules/resumes/router.py](app/modules/resumes/router.py))
  - POST /api/v1/resumes - Create resume
  - GET /api/v1/resumes - List resumes (with pagination and filters)
  - GET /api/v1/resumes/formal-limit - Check quota
  - GET /api/v1/resumes/{resume_id} - Get resume detail
  - PUT /api/v1/resumes/{resume_id} - Update content
  - PATCH /api/v1/resumes/{resume_id}/title - Update title
  - PATCH /api/v1/resumes/{resume_id}/finalize - Convert to formal
  - DELETE /api/v1/resumes/{resume_id} - Soft delete
  - GET /api/v1/resumes/{resume_id}/versions - Version history
- ✅ Updated User model to add resume relationships ([app/modules/auth/models.py](app/modules/auth/models.py))
- ✅ Created auth dependencies module ([app/modules/auth/dependencies.py](app/modules/auth/dependencies.py))
- ✅ Registered Resume router in API v1 ([app/api/v1/router.py](app/api/v1/router.py))
- ✅ Generated database migration for resumes and documents tables
  - Migration file: `20251124_0050_2b8ba0e2d92a_add_resumes_and_documents_tables.py`

**Key Features Implemented:**
- Content deduplication via SHA-256 hashing
- Version chain management (root_id → parent_id → children)
- Formal resume quota system (max 3 per user)
- Draft/formal workflow
- Soft delete for resumes
- Full JWT authentication on all endpoints

**Issues Fixed:**
- ✅ Added primary key fields to Document and Resume models
- ✅ Fixed user_id type mismatch (String → int)
- ✅ Fixed JSON column definition (dict → JSON)
- ✅ Renamed reserved field name (metadata → extra_metadata)
- ✅ Cleaned up auto-generated migration (removed unrelated table operations)

**Pending:**
- Apply database migration (user to execute manually)

**Migration Command:**
```bash
cd backend
.venv\Scripts\alembic.exe upgrade head
```

---

### 2025-11-24 - Job Browsing Module Frontend Completed

**Completed Tasks:**

**Frontend Implementation:**
- ✅ Created `docs/frontend_development_guide.md` for development standards
- ✅ Built Core UI components (`Badge`, `Skeleton`, `Separator`, `Sheet`, `Checkbox`, `Select`, `Accordion`, `ScrollArea`)
- ✅ Implemented `JobCard`, `JobSearch`, `JobFilters`, `JobPagination` components
- ✅ Built `JobListingPage` with URL-based state management for filters
- ✅ Built `JobDetailPage` with comprehensive job information display
- ✅ Configured routes for `/jobs` and `/jobs/:jobId`
- ✅ Resolved React Router v7 future flag warnings
- ✅ Refined Auth UI (Alerts for errors, removed custom password strength bars)

**Integration:**
- ✅ Connected Frontend to Backend Job API
- ✅ Verified build success

**Issues Resolved:**
- Fixed TypeScript `import type` errors for build compliance

### 2025-11-24 - Job Browsing Module Backend Completed

**Completed Tasks:**

**Backend Implementation:**
- ✅ Created SeekJob model for read-only access to seek_jobs table (`app/modules/jobs/models.py`)
- ✅ Mapped 70+ fields from external crawler system's seek_jobs table
- ✅ Added database indexes for optimized querying (source_id, title, listed_at, location_city, etc.)
- ✅ Implemented Pydantic schemas for API requests/responses (`app/modules/jobs/schemas.py`)
  - JobBase: List display fields
  - JobDetail: Complete job information
  - JobListResponse: Paginated response format
  - JobFiltersRequest: Filter parameters
  - JobFiltersOptions: Available filter dropdown options
- ✅ Built JobService with core business logic (`app/modules/jobs/service.py`)
  - get_jobs(): Pagination + multi-dimension filtering + full-text search
  - get_job_by_id(): Job detail retrieval
  - get_filter_options(): Dynamic filter options
  - get_similar_jobs(): Same company + classification recommendations
- ✅ Created Job API endpoints (`app/modules/jobs/router.py`)
  - GET /api/v1/jobs - Paginated job list with filters
  - GET /api/v1/jobs/filters - Filter dropdown options
  - GET /api/v1/jobs/{job_id} - Job details
  - GET /api/v1/jobs/{job_id}/similar - Similar jobs
- ✅ Registered Job router in API v1 (`app/api/v1/router.py`)

**Frontend Implementation:**
- ✅ Created TypeScript type definitions (`src/types/job.ts`)
  - Job, JobDetail, JobListResponse, JobFiltersRequest, JobFiltersOptions
- ✅ Built Job API client (`src/api/jobs.ts`)
  - getJobs(), getJobById(), getSimilarJobs(), getFilterOptions()
- ✅ Implemented React Query hooks (`src/features/jobs/hooks/useJobs.ts`)
  - useJobs(), useJobDetail(), useSimilarJobs(), useJobFilterOptions()
- ✅ Added shadcn/ui components
  - Badge component (`src/components/ui/badge.tsx`)
  - Skeleton component (`src/components/ui/skeleton.tsx`)

**Key Features Implemented:**
- Full-text search across title, abstract, and content
- Multi-select filtering (location, work type, company)
- Date range filtering (listed_after/listed_before)
- Sorting by listed_at or title (asc/desc)
- Server-side pagination (configurable page size, max 100)
- Similar job recommendations based on company and classification

---

### 2025-11-23 - Authentication System Completed

**Completed Tasks:**

**Backend Implementation:**
- ✅ Created User model with SQLAlchemy (`app/modules/auth/models.py`)
- ✅ Implemented JWT token generation and validation (`app/core/security.py`)
- ✅ Created password hashing utilities with bcrypt
- ✅ Built authentication service (register, login) (`app/modules/auth/service.py`)
- ✅ Implemented get_current_user dependency
- ✅ Created auth API endpoints (`app/modules/auth/router.py`)
- ✅ Generated and applied Alembic migration for User table
- ✅ Fixed bcrypt compatibility issues (downgraded to 4.0.1)

**Frontend Implementation:**
- ✅ Created auth API client (`src/api/auth.ts`)
- ✅ Implemented Zustand auth store with localStorage persistence (`src/store/authStore.ts`)
- ✅ Built Login page component (`src/pages/Login.tsx`)
- ✅ Built Register page component (`src/pages/Register.tsx`)
- ✅ Set up React Router with protected routes
- ✅ Implemented ProtectedRoute wrapper component
- ✅ Imported shadcn/ui components (Button, Input, Card, Form, Label)

**Integration Testing:**
- ✅ Tested user registration flow
- ✅ Tested user login flow
- ✅ Verified JWT token storage in localStorage
- ✅ Tested protected route access control
- ✅ Verified token-based authentication in API requests

**Issues Resolved:**
- Fixed bcrypt compatibility issue by downgrading from 4.2.1 to 4.0.1
- Resolved circular import warnings in backend modules
- Downgraded Tailwind CSS from v4 to v3.4.18 for better shadcn/ui compatibility

---

### 2025-01-22 - Project Initialization

**Completed Tasks:**

**Backend Setup:**
- Created FastAPI project structure with async SQLAlchemy 2.0
- Configured Alembic for database migrations
- Implemented core configuration with Pydantic Settings
- Created base models and global enums
- Set up CORS middleware and exception handlers
- Added health check endpoint at `/health`

**Frontend Setup:**
- Initialized Vite + React + TypeScript project
- Upgraded to Tailwind CSS v4 with @tailwindcss/postcss
- Configured Axios client with auth interceptors
- Set up TanStack Query (React Query)
- Created project directory structure
- Configured API proxy in Vite

**Infrastructure:**
- Adopted `uv` as Python package manager
- Adopted `pnpm` as Node.js package manager
- Created environment configuration files
- Wrote comprehensive documentation (README.md, TAILWIND-V4.md, FIXES.md)

**Key Changes:**
- Replaced Poetry with `uv` for better performance
- Replaced npm with `pnpm` for faster installs
- Chose Tailwind CSS v4 for modern features

---

## Next Steps

### Stage 3: Application Module
- **Backend/Frontend**:
  - Verify application resume/cover letter PDF downloads and cover letter template rendering
- **Backend**:
  - Design Application model (user_id, job_id, resume_id, status)
  - Create API endpoints for applying to jobs
  - Implement file upload for resumes (if not already done)
- **Frontend**:
  - Build "Apply Now" modal/flow
  - Create "My Applications" page
  - Integrate Resume upload

### Stage 4: User Profile & Settings
- **Frontend**:
  - Build User Profile page
  - Settings page (password change, notification prefs)

## Known Issues

None at this stage.

---

## Technical Notes

- Using Tailwind CSS v3.4.18 with traditional `@tailwind` directives
- Custom styles are wrapped in `@layer` directives for proper CSS ordering
- shadcn/ui components use CSS variables for theming (defined in `src/index.css`)
- Database migrations managed by Alembic (async mode)
- JWT tokens stored in localStorage with automatic axios interceptor injection
- Celery workers will be configured in later stages

### 2026-03-13 - Celery Async Loop Concurrency Fix (Event Loop Re-entry)

**Completed Tasks:**
- Investigated worker failures in `backend/logs/celery-worker.log` for `This event loop is already running`.
- Confirmed failure path in async task base wrappers and DB tracking hooks (`run_until_complete` re-entry + cross-loop fallback).
- Refactored worker async loop lifecycle:
  - introduced a dedicated background asyncio loop thread.
  - added sync bridge utility `run_coroutine_sync(...)` for Celery sync context.
  - added safe worker startup/shutdown handling for loop and `engine.dispose()`.
- Updated async task execution and DB hook execution to use the shared sync bridge.
- Performed syntax verification via compileall for changed backend files.

### 2026-03-13 - Task Monitor: Running Task Elapsed Time Display

**Completed Tasks:**
- Added live elapsed-time display for tasks in `Running` status on the admin task list card.
- Elapsed time now updates every second based on `startedAt` (format: `Xs`, `Xm Ys`, `Xh Ym Zs`).
- Kept the change scoped to `TaskCard` rendering logic only.
- Fixed timezone parsing on admin task card for API datetime strings without timezone suffix:
  - treat naive datetime string as UTC before duration/relative-time calculation
  - corrected Running duration and Created relative time drift (e.g., NZ +13h offset)

### 2026-03-13 - Timezone Audit & Naive Datetime Remediation (Code + Data)

**Completed Tasks:**
- Audited backend for naive datetime usage (`utcnow()` / `now()` without timezone).
- Replaced naive timestamp writes with UTC-aware timestamps in runtime-critical modules:
  - workflow task state writes (`started_at`, `completed_at`)
  - outbox retry/publish timestamps
  - application progress `last_update`
  - resume soft-delete and resume-skill update timestamps
  - jobs repository time-window filters
- Normalized resume PDF metadata generation time to explicit UTC label.
- Added Alembic migration to repair schema/data for timezone consistency:
  - conditionally promote key columns from `timestamp without time zone` to `timestamptz` (interpreting existing values as UTC)
  - backfill `applications.tailoring_progress.last_update` naive ISO strings by appending `Z`
  - migration file: `20260313_1100_d9f2a8c4e6b1_fix_naive_timestamps.py`
- Added Running duration anomaly correction on admin task card:
  - detect historical `startedAt` offsets (~10-14h behind `createdAt`)
  - auto-normalize displayed running duration for affected legacy rows
- Extended timezone migration with data repair SQL for shifted `task_executions.started_at` in `Running` status.
