# User Dashboard Implementation Plan

**Version:** 1.0
**Date:** 2026-03-16
**Status:** Proposed

---

## Background

The current authenticated user area already supports the core workflow:
- browse jobs;
- save and review jobs;
- create and manage applications;
- manage resumes;
- manage user skills.

However, the `/dashboard` route is still a placeholder. This creates a gap between login and the user's next meaningful action. A proper user dashboard should act as the operational home page for job seekers, not as a generic analytics screen.

This document defines a concrete implementation plan for the normal user dashboard based on features that already exist in the current codebase.

---

## Current Product Baseline

### Implemented user-facing modules

- Jobs
  - listing, filtering, viewed state, saved state, job detail, similar jobs
  - match APIs for user-specific recommended jobs
- Applications
  - listing, detail view, status transitions, retry generation, document export
- Resumes
  - list, create, edit, finalize, export
- Skills
  - list, add, edit, delete, sync from resumes

### Current route situation

- `/dashboard` exists but uses a placeholder page
- `/jobs`, `/applications`, `/resumes`, `/skills` are implemented and usable

### Important constraint

There is no dedicated backend aggregation endpoint for a user dashboard today. The MVP dashboard should therefore be implemented by composing existing APIs on the frontend first.

---

## Dashboard Goal

The dashboard should answer three questions immediately after login:

1. What should I do next?
2. Which jobs are most worth my attention?
3. Am I ready to apply with high-quality materials?

This means the page should prioritize actionability over pure reporting.

---

## Design Principles

- Action-first: surface the next best action before secondary metrics.
- Grounded in existing data: do not invent widgets that current APIs cannot support.
- Lightweight aggregation: avoid adding backend work for the first version unless strictly necessary.
- Clear hierarchy: urgent application tasks first, opportunity discovery second, asset readiness third.
- Responsive by default: desktop two-column layout, mobile stacked sections.

---

## MVP Scope

### In scope

- replace placeholder `/dashboard` with a real page;
- show a personalized hero and quick actions;
- show summary metrics derived from current APIs;
- show a single "priority action" card;
- show a compact application progress section;
- show recommended jobs from existing job match APIs;
- show resume readiness summary;
- show skill library summary;
- show saved or recently viewed job shortcuts.

### Out of scope

- new backend dashboard endpoint;
- new analytics tables or event tracking;
- interview preparation center;
- full profile/settings surfaces;
- time-series charts for normal users;
- quota billing visualization beyond simple reminders;
- kanban board embedded in dashboard.

---

## Information Architecture

### Section 1: Hero

Purpose:
- orient the user;
- frame today's focus;
- provide direct entry points.

Content:
- greeting with user name;
- short dynamic sentence based on current state;
- primary actions:
  - `Browse Jobs`
  - `Manage Resumes`

Dynamic message priority:
1. if there are `Ready` applications: prompt user to apply;
2. else if there are `Failed` applications: prompt retry;
3. else if there are active `Pending` or `Tailoring` applications: prompt review;
4. else if there are strong job matches: prompt job exploration;
5. else prompt resume preparation.

### Section 2: Summary Metrics

Recommended cards:
- Active Applications
- Ready to Apply
- Saved Jobs
- Final Resumes

Notes:
- keep these cards compact and uniform;
- each card should link to the relevant module page.

### Section 3: Priority Action

Purpose:
- reduce decision fatigue by elevating one actionable item.

Priority rule:
1. first `Ready` application;
2. first `Failed` application;
3. newest `Pending` or `Tailoring` application;
4. highest-score unmatched job;
5. newest draft resume if no finalized resume exists.

Card content:
- title;
- one-line reason;
- single main CTA;
- optional secondary link.

### Section 4: Application Progress Snapshot

Purpose:
- give a fast operational view without replacing the full applications page.

Content:
- status count row:
  - Pending
  - Tailoring
  - Ready
  - Applied
  - Interviewing
  - Offer
  - Rejected
- list of 3-5 applications that need attention

Each application row should include:
- job title;
- company;
- status badge;
- expired badge if applicable;
- relevant action:
  - `Open`
  - `Apply`
  - `Retry`

### Section 5: Recommended Jobs

Purpose:
- drive users back into high-value opportunities.

Data source:
- existing user job match API

Recommended presentation:
- default tab: `Best Matches`
- secondary tab: `Saved Jobs`

Each job card should include:
- title;
- company;
- location;
- skill match score;
- recommended resume if available;
- viewed/applied state if available;
- CTA:
  - `View Job`
  - optional `Start Application`

Fallback:
- if no match data is available, show saved jobs instead.

### Section 6: Resume Readiness

Purpose:
- show whether the user is ready to apply with usable materials.

Content:
- finalized resume count;
- draft resume count;
- most recently updated resume;
- prompt if there are no finalized resumes.

Primary action:
- `Manage Resumes`

### Section 7: Skills Overview

Purpose:
- reinforce value of the skill library and explain match quality.

Content:
- total skills;
- manual skills;
- synced skills;
- top skill tags;
- `Manage Skills` button.

### Section 8: Quick Access

Purpose:
- keep navigation friction low.

Links:
- Jobs
- Applications
- Resumes
- Skills

---

## Layout Plan

### Desktop

- 12-column grid
- left column: 8 columns
- right column: 4 columns

Recommended arrangement:
- full width:
  - Hero
  - Summary Metrics
- left:
  - Priority Action
  - Application Progress Snapshot
  - Recommended Jobs
- right:
  - Resume Readiness
  - Skills Overview
  - Quick Access

### Mobile

- single column stack
- order:
  1. Hero
  2. Priority Action
  3. Summary Metrics
  4. Application Progress Snapshot
  5. Recommended Jobs
  6. Resume Readiness
  7. Skills Overview
  8. Quick Access

---

## Data Mapping Plan

The MVP should reuse existing APIs instead of introducing a new backend dashboard endpoint.

### Existing frontend data sources

- Auth store
  - user name and role
- Applications API
  - list data for status counts and priority action
- Jobs API
  - saved jobs list
  - job matches
- Resumes API
  - resume counts and readiness summary
- Skills API
  - skills totals and tags

### Proposed frontend aggregation

- one page-level hook should orchestrate dashboard queries;
- derived values should be calculated in the dashboard layer, not duplicated in each card;
- cards should remain presentational and receive already-shaped props.

### Recommended initial query strategy

- applications:
  - fetch first page with page size large enough for dashboard summary needs
- job matches:
  - fetch top matches only
- saved jobs:
  - fetch first page only
- resumes:
  - fetch current list
- skills:
  - fetch current list

### Suggested future backend optimization

If dashboard performance or request fan-out becomes a problem, add:
- `GET /api/v1/dashboard/summary`

That endpoint can aggregate:
- application counts by status;
- top priority application;
- top matched jobs;
- resume readiness summary;
- skills summary.

This backend endpoint is explicitly phase 2, not required for MVP.

---

## UI Components Plan

### New page

- `frontend/src/features/dashboard/UserDashboardPage.tsx`

### New hooks

- `frontend/src/features/dashboard/hooks/useUserDashboard.ts`

Responsibilities:
- load all dashboard data;
- calculate derived metrics;
- produce priority action;
- expose loading and partial-error states.

### New components

- `frontend/src/features/dashboard/components/DashboardHero.tsx`
- `frontend/src/features/dashboard/components/DashboardMetricCards.tsx`
- `frontend/src/features/dashboard/components/PriorityActionCard.tsx`
- `frontend/src/features/dashboard/components/ApplicationPipelineCard.tsx`
- `frontend/src/features/dashboard/components/RecommendedJobsCard.tsx`
- `frontend/src/features/dashboard/components/ResumeReadinessCard.tsx`
- `frontend/src/features/dashboard/components/SkillsOverviewCard.tsx`
- `frontend/src/features/dashboard/components/QuickLinksCard.tsx`

### Reuse opportunities

- existing button, card, badge, skeleton, tooltip components
- existing application status badge component
- existing job/resume data formatting helpers where possible

---

## Interaction Details

### Loading

- hero and metric cards should show skeletons;
- avoid blocking the whole page with one full-screen loader once shell layout is mounted;
- allow independent section loading where possible.

### Empty states

- no applications:
  - show CTA to browse jobs
- no finalized resumes:
  - show CTA to create or finalize a resume
- no matches:
  - show saved jobs or browse jobs CTA
- no skills:
  - show CTA to sync from resumes or add skills manually

### Error handling

- partial failure should not blank the full dashboard;
- each card can show a small inline error and fallback CTA;
- avoid noisy toast usage for initial page data fetch failure.

---

## Styling Direction

The user dashboard should feel more like a focused workbench than a marketing page.

Recommended visual direction:
- neutral slate background with white cards;
- indigo as the main accent to match current app patterns;
- green for `Ready` and positive progress;
- amber or blue for in-progress states;
- red for failed or expired states;
- restrained gradients only in the hero area.

The page should remain visually consistent with the existing jobs/applications/resumes modules instead of introducing a separate design language.

---

## Implementation Sequence

### Phase 1: Page foundation

1. Create dashboard feature folder.
2. Add `UserDashboardPage.tsx`.
3. Replace `/dashboard` placeholder route with the new page.
4. Build static skeleton layout first.

### Phase 2: Data aggregation

1. Create `useUserDashboard`.
2. Wire existing queries:
   - applications
   - job matches
   - saved jobs
   - resumes
   - skills
3. Add derived selectors:
   - metrics
   - status counts
   - top priority action
   - top recommendations

### Phase 3: Core cards

1. Hero
2. Summary metrics
3. Priority action
4. Application progress snapshot
5. Recommended jobs

### Phase 4: Supporting cards

1. Resume readiness
2. Skills overview
3. Quick access
4. Empty states and partial-error states

### Phase 5: Polish and validation

1. Responsive adjustments
2. Loading state polish
3. Link and CTA validation
4. Final visual alignment with main layout

---

## File-Level Change Plan

### Must create

- `frontend/src/features/dashboard/UserDashboardPage.tsx`
- `frontend/src/features/dashboard/hooks/useUserDashboard.ts`
- `frontend/src/features/dashboard/components/DashboardHero.tsx`
- `frontend/src/features/dashboard/components/DashboardMetricCards.tsx`
- `frontend/src/features/dashboard/components/PriorityActionCard.tsx`
- `frontend/src/features/dashboard/components/ApplicationPipelineCard.tsx`
- `frontend/src/features/dashboard/components/RecommendedJobsCard.tsx`
- `frontend/src/features/dashboard/components/ResumeReadinessCard.tsx`
- `frontend/src/features/dashboard/components/SkillsOverviewCard.tsx`
- `frontend/src/features/dashboard/components/QuickLinksCard.tsx`

### Must modify

- `frontend/src/App.tsx`
  - replace placeholder route for `/dashboard`

### Optional future additions

- `frontend/src/features/dashboard/types.ts`
- `frontend/src/features/dashboard/utils.ts`

---

## Acceptance Criteria

- `/dashboard` is a real user dashboard, not a placeholder.
- User sees at least one clear next action on first load.
- Dashboard shows key counts for applications, saved jobs, and resumes.
- Dashboard surfaces top matched jobs using existing match data.
- Dashboard surfaces status-aware application actions.
- Dashboard works on both desktop and mobile layouts.
- Dashboard still remains usable if one secondary data source fails.

---

## Risks and Mitigations

### Risk: too many parallel frontend requests

Mitigation:
- keep page queries small;
- use first-page summaries only;
- move to a backend aggregate endpoint later if needed.

### Risk: status counts may be incomplete if only one page of applications is loaded

Mitigation:
- for MVP, either:
  - fetch a sufficiently large page size, or
  - add a lightweight application stats endpoint later.

Recommended choice:
- use a larger page size for MVP if current dataset size remains manageable.

### Risk: dashboard becomes a duplicate of the applications page

Mitigation:
- keep dashboard sections compact and action-oriented;
- never embed the full list or the full management workflow.

---

## Phase 2 Opportunities

- add dedicated backend dashboard summary endpoint;
- add interview preparation panel when that module is available;
- add quota summary when profile/settings and quota surfaces are ready;
- add weekly trend charts for applications and response rate;
- add user-configurable widgets if dashboard complexity grows.

---

## Proposed Delivery Order

If implemented now, the recommended execution order is:

1. dashboard route replacement;
2. aggregated data hook;
3. hero + metrics + priority action;
4. application snapshot;
5. recommended jobs;
6. resume and skills cards;
7. responsive and visual polish.

This order delivers usable value early and keeps regression risk low.
