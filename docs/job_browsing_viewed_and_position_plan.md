# Job Browsing: Viewed State and List Position Plan

## Background
Users browse a large number of jobs and need two improvements:
1. avoid repeatedly opening jobs they already viewed;
2. return to the correct place in the list after opening details.

## UX Decisions
- Mark viewed state asynchronously and non-blocking (never block detail rendering).
- Preserve position per list context (view mode + query params).
- When filters/search/sort/page context changes, treat it as a new context and reset to top.
- For explicit detail -> back flow within the same context, restore to the previously viewed job anchor and highlight it.

## Scope
- Backend:
  - persist user viewed records;
  - provide viewed status in job list payload;
  - support `view_status` filter (`all`, `viewed`, `unviewed`);
  - add endpoint to mark viewed and get single-job viewed status.
- Frontend:
  - optimistic, fire-and-forget viewed marking when detail opens;
  - render viewed badge on cards;
  - preserve/restore per-context list position;
  - reset to top when current context changed.

## Backend Design

### Data Model
New table: `user_job_views`
- `id` (uuid string)
- `user_id` (FK users.id)
- `job_id` (FK seek_jobs.id)
- `first_viewed_at` (timestamptz)
- `last_viewed_at` (timestamptz)
- `view_count` (int, default 1)
- `created_at` / `updated_at`

Constraints and indexes:
- unique `(user_id, job_id)`
- index `(user_id, last_viewed_at desc)`
- index `(user_id, job_id)`

### API Changes
- `GET /api/v1/jobs`
  - add query: `view_status=all|viewed|unviewed`
  - each item includes:
    - `is_viewed`
    - `last_viewed_at`
- `POST /api/v1/jobs/{job_id}/viewed`
  - upsert viewed state:
    - first time: set `first_viewed_at = last_viewed_at = now`, `view_count = 1`
    - repeat: set `last_viewed_at = now`, `view_count += 1`
- `GET /api/v1/jobs/{job_id}/viewed`
  - return current viewed status for this user and job

### Service/Repository Rules
- `mark_viewed` must be idempotent under concurrent calls (upsert + unique constraint fallback).
- `get_jobs` should filter by viewed status without breaking existing pagination/sort semantics.
- viewed metadata should be fetched in batch for current page results.

## Frontend Design

### Viewed Marking (Non-blocking)
- On detail page load, call mark-viewed mutation in background.
- Do not await before rendering page content.
- Failure is silent (no blocking toast).
- Optimistically update job query caches for the same job id.

### Position Context
Context key:
- `jobs:list:{viewMode}:{normalizedQueryWithoutPage}`

Stored session data:
- `anchorJobId`
- `scrollY`
- `updatedAt`

### Position Behavior
- Before navigating from list card to detail:
  - persist `anchorJobId` and current `scrollY` for current context key.
- On list page mount/data ready:
  - if navigation is a return from detail and context key matches:
    - try scroll to anchor card;
    - fallback to stored `scrollY`.
  - apply temporary highlight to restored job card.
- If context changes (filters/search/sort/view mode), clear restore intent and scroll to top.

## Implementation Steps
1. Add backend model + Alembic migration.
2. Add repository and service methods for viewed upsert/status/map.
3. Extend jobs list filtering and response schema with viewed fields.
4. Add viewed endpoints in jobs router.
5. Extend frontend types/api/hooks.
6. Implement detail mark-viewed mutation and cache updates.
7. Implement list position state and restoration logic.
8. Add viewed badge rendering in job cards.
9. Validate flows and update progress/issues docs.

## Acceptance Criteria
- Opening a job detail marks it viewed without delaying detail render.
- Job list can filter by viewed/unviewed.
- Returning from detail restores the correct list position in the same context.
- Changing filters/search/sort/view mode resets to top.
- Viewed badge is visible in list cards.
