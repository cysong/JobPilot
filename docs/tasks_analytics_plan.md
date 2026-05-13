# Tasks Analytics Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new admin analytics page at `/admin/tasks/chart`, linked from the dashboard `tasks` card, that visualises daily task volume + failure rate (stacked bar/area + dashed %-line overlay) and daily execution-time stats (avg/p50/p95 lines) per task type.

**Architecture:** Two new backend GET endpoints under `/admin/tasks/*` aggregate `task_executions` rows in the user's app timezone, returning per-day × per-`task_name` counts/failure/duration percentiles. Two React Query hooks feed a single new page modeled on `AdminJobsChartPage.tsx`, reusing its `ChartStateBox`, range button group, legend toggles, and Recharts patterns.

**Tech Stack:** FastAPI + SQLAlchemy async (Postgres `percentile_cont`), Pydantic v2 schemas, React 18 + TypeScript + Recharts (`ComposedChart`, `LineChart`), TanStack Query.

**Testing strategy:** Backend `AdminService` aggregation methods have no precedent for unit tests in this codebase (no existing `test_admin*.py`), and the logic is dominated by SQL. We verify backend correctness via curl with seeded data and the in-browser chart rendering. Pure helper logic (e.g., failure-rate divide-by-zero handling) is asserted by docstring + smoke output inspection. Frontend follows the existing convention of no component unit tests.

---

## File Structure

**Backend (modify):**
- `backend/app/modules/admin/schemas.py` — add 4 response models (trend/exec-time × point/series + responses)
- `backend/app/modules/admin/service.py` — add `get_tasks_daily_trend()` and `get_tasks_execution_time()` static methods on `AdminService`
- `backend/app/modules/admin/router.py` — register `GET /admin/tasks/daily-trend` and `GET /admin/tasks/execution-time`

**Frontend (create):**
- `frontend/src/features/admin/hooks/useTasksDailyTrend.ts`
- `frontend/src/features/admin/hooks/useTasksExecutionTime.ts`
- `frontend/src/features/admin/pages/AdminTasksChartPage.tsx`

**Frontend (modify):**
- `frontend/src/features/admin/types.ts` — append 4 response types
- `frontend/src/api/admin.ts` — add `getTasksDailyTrend` and `getTasksExecutionTime`
- `frontend/src/features/admin/components/DashboardStats.tsx` — add `href: '/admin/tasks/chart'` to tasks card config
- `frontend/src/App.tsx` — register new route

---

## Task 1: Backend response schemas

**Files:**
- Modify: `backend/app/modules/admin/schemas.py`

- [ ] **Step 1: Append response models for the two endpoints**

Add at the end of `backend/app/modules/admin/schemas.py` (after the `TaskStatisticsResponse` block):

```python
# ===== Tasks Analytics — daily count + failure rate =====
class TasksDailyTrendPoint(AdminBase):
    date: str
    count: int
    failed: int
    failure_rate: Optional[float] = Field(None, alias="failureRate")


class TasksDailyTrendSeries(AdminBase):
    name: str
    points: List[TasksDailyTrendPoint]


class TasksDailyTrendResponse(AdminBase):
    timezone: str
    start_date: str = Field(..., alias="startDate")
    end_date: str = Field(..., alias="endDate")
    task_types: List[str] = Field(..., alias="taskTypes")
    series: List[TasksDailyTrendSeries]


# ===== Tasks Analytics — execution time percentiles =====
class TasksExecutionTimePoint(AdminBase):
    date: str
    avg_ms: float = Field(..., alias="avgMs")
    p50_ms: float = Field(..., alias="p50Ms")
    p95_ms: float = Field(..., alias="p95Ms")
    sample_count: int = Field(..., alias="sampleCount")


class TasksExecutionTimeSeries(AdminBase):
    name: str
    points: List[TasksExecutionTimePoint]


class TasksExecutionTimeResponse(AdminBase):
    timezone: str
    start_date: str = Field(..., alias="startDate")
    end_date: str = Field(..., alias="endDate")
    task_types: List[str] = Field(..., alias="taskTypes")
    series: List[TasksExecutionTimeSeries]
```

`failure_rate` is `Optional[float]` so the backend can emit `null` when `count == 0` for a day/type cell. `TasksExecutionTimePoint` has no nullable stats — points are only emitted when `sample_count > 0` (gaps in the time series).

- [ ] **Step 2: Verify imports compile**

Run: `python -c "from app.modules.admin.schemas import TasksDailyTrendResponse, TasksExecutionTimeResponse; print('ok')"` from `backend/`.

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/admin/schemas.py
git commit -m "feat(admin): add tasks analytics response schemas"
```

---

## Task 2: Backend service — daily trend

**Files:**
- Modify: `backend/app/modules/admin/service.py`

- [ ] **Step 1: Add imports**

At the top of `service.py`, in the existing import block from `app.modules.admin.schemas`, append the four new symbols:

```python
from app.modules.admin.schemas import (
    AIUsageDailyTrendPoint,
    AIUsageDailyTrendResponse,
    AIUsageDailyTrendSeries,
    DashboardStats,
    FloatMetricCount,
    JobsDailyTrendPoint,
    JobsDailyTrendResponse,
    JobsDailyTrendSeries,
    JobsTimeScatterPoint,
    JobsTimeScatterResponse,
    MetricCount,
    TaskMetric,
    TasksDailyTrendPoint,
    TasksDailyTrendResponse,
    TasksDailyTrendSeries,
    TasksExecutionTimePoint,
    TasksExecutionTimeResponse,
    TasksExecutionTimeSeries,
)
```

Also confirm `TaskExecution` and `TaskStatus` are already imported (they are, from earlier code: lines 29–30 in current `service.py`).

Add `case` to the SQLAlchemy imports near line 7:

```python
from sqlalchemy import case, cast, Date, func, select
```

- [ ] **Step 2: Append `get_tasks_daily_trend` method on `AdminService`**

Add this method to the `AdminService` class, near the other trend methods (after `get_jobs_time_scatter`, before `get_ai_tokens_daily_trend`):

```python
    @staticmethod
    @jcache("admin:tasks:daily-trend:{days}", ttl=300)
    async def get_tasks_daily_trend(db: AsyncSession, days: int = 30) -> TasksDailyTrendResponse:
        """Return daily task counts and failed counts per task_name, plus a Total series.

        Buckets by user's app timezone. ``failure_rate`` is ``None`` when count is 0
        so the frontend can break failure-rate lines at empty days. The ``Total``
        series sums across all task types and exposes the overall failure rate.
        """
        days = max(7, min(days, 90))

        app_tz, tz_name = AdminService._app_timezone()

        today_local = datetime.now(app_tz).date()
        start_date = today_local - timedelta(days=days - 1)
        end_date = today_local

        start_local_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=app_tz)
        end_exclusive_local_dt = datetime.combine(
            end_date + timedelta(days=1), datetime.min.time(), tzinfo=app_tz
        )

        start_utc = start_local_dt.astimezone(timezone.utc)
        end_exclusive_utc = end_exclusive_local_dt.astimezone(timezone.utc)

        local_date = cast(func.timezone(tz_name, TaskExecution.created_at), Date)
        failed_expr = case((TaskExecution.status == TaskStatus.FAILED, 1), else_=0)

        rows = (
            await db.execute(
                select(
                    local_date.label("local_date"),
                    TaskExecution.task_name.label("task_name"),
                    func.count(TaskExecution.id).label("task_count"),
                    func.coalesce(func.sum(failed_expr), 0).label("failed_count"),
                )
                .where(
                    TaskExecution.created_at.isnot(None),
                    TaskExecution.created_at >= start_utc,
                    TaskExecution.created_at < end_exclusive_utc,
                )
                .group_by("local_date", "task_name")
                .order_by("local_date", "task_name")
            )
        ).all()

        # by_type[task_name][date] -> (count, failed)
        by_type: dict[str, dict[date, tuple[int, int]]] = {}
        all_types: set[str] = set()

        for local_day, task_name, task_count, failed_count in rows:
            if local_day is None or not task_name:
                continue
            name = str(task_name)
            all_types.add(name)
            by_type.setdefault(name, {})[local_day] = (
                int(task_count or 0),
                int(failed_count or 0),
            )

        sorted_types = sorted(all_types)
        dates = [start_date + timedelta(days=i) for i in range(days)]

        def make_point(count: int, failed: int, day: date) -> TasksDailyTrendPoint:
            rate = (failed / count) if count > 0 else None
            return TasksDailyTrendPoint(
                date=day.isoformat(),
                count=count,
                failed=failed,
                failure_rate=rate,
            )

        series: list[TasksDailyTrendSeries] = []

        total_points: list[TasksDailyTrendPoint] = []
        for day in dates:
            day_count = 0
            day_failed = 0
            for name in sorted_types:
                count, failed = by_type.get(name, {}).get(day, (0, 0))
                day_count += count
                day_failed += failed
            total_points.append(make_point(day_count, day_failed, day))
        series.append(TasksDailyTrendSeries(name="Total", points=total_points))

        for name in sorted_types:
            points = []
            for day in dates:
                count, failed = by_type.get(name, {}).get(day, (0, 0))
                points.append(make_point(count, failed, day))
            series.append(TasksDailyTrendSeries(name=name, points=points))

        return TasksDailyTrendResponse(
            timezone=tz_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            task_types=sorted_types,
            series=series,
        )
```

- [ ] **Step 3: Verify Python imports / syntax**

Run from `backend/`: `python -c "from app.modules.admin.service import AdminService; print(hasattr(AdminService, 'get_tasks_daily_trend'))"`

Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/admin/service.py
git commit -m "feat(admin): aggregate tasks daily trend with failure rate"
```

---

## Task 3: Backend service — execution time percentiles

**Files:**
- Modify: `backend/app/modules/admin/service.py`

- [ ] **Step 1: Append `get_tasks_execution_time` method**

Add immediately after `get_tasks_daily_trend` in `AdminService`:

```python
    @staticmethod
    @jcache("admin:tasks:execution-time:{days}", ttl=300)
    async def get_tasks_execution_time(db: AsyncSession, days: int = 30) -> TasksExecutionTimeResponse:
        """Return per-day avg/p50/p95 execution_time_ms grouped by task_name.

        Only ``status = SUCCESS`` rows contribute; failed tasks have unreliable
        durations. A ``(date, task_name)`` cell with no successful samples is
        omitted from that series' points — the frontend uses ``connectNulls=false``
        to break the line at the gap.
        """
        days = max(7, min(days, 90))

        app_tz, tz_name = AdminService._app_timezone()

        today_local = datetime.now(app_tz).date()
        start_date = today_local - timedelta(days=days - 1)
        end_date = today_local

        start_local_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=app_tz)
        end_exclusive_local_dt = datetime.combine(
            end_date + timedelta(days=1), datetime.min.time(), tzinfo=app_tz
        )

        start_utc = start_local_dt.astimezone(timezone.utc)
        end_exclusive_utc = end_exclusive_local_dt.astimezone(timezone.utc)

        local_date = cast(func.timezone(tz_name, TaskExecution.created_at), Date)
        duration = TaskExecution.execution_time_ms

        rows = (
            await db.execute(
                select(
                    local_date.label("local_date"),
                    TaskExecution.task_name.label("task_name"),
                    func.avg(duration).label("avg_ms"),
                    func.percentile_cont(0.5).within_group(duration.asc()).label("p50_ms"),
                    func.percentile_cont(0.95).within_group(duration.asc()).label("p95_ms"),
                    func.count(TaskExecution.id).label("sample_count"),
                )
                .where(
                    TaskExecution.created_at.isnot(None),
                    TaskExecution.created_at >= start_utc,
                    TaskExecution.created_at < end_exclusive_utc,
                    TaskExecution.status == TaskStatus.SUCCESS,
                    TaskExecution.execution_time_ms.isnot(None),
                )
                .group_by("local_date", "task_name")
                .order_by("local_date", "task_name")
            )
        ).all()

        # by_type[task_name] -> list of points (chronological)
        by_type: dict[str, list[TasksExecutionTimePoint]] = {}
        all_types: set[str] = set()

        for local_day, task_name, avg_ms, p50_ms, p95_ms, sample_count in rows:
            if local_day is None or not task_name:
                continue
            name = str(task_name)
            all_types.add(name)
            by_type.setdefault(name, []).append(
                TasksExecutionTimePoint(
                    date=local_day.isoformat(),
                    avg_ms=float(avg_ms or 0.0),
                    p50_ms=float(p50_ms or 0.0),
                    p95_ms=float(p95_ms or 0.0),
                    sample_count=int(sample_count or 0),
                )
            )

        sorted_types = sorted(all_types)

        series: list[TasksExecutionTimeSeries] = [
            TasksExecutionTimeSeries(name=name, points=by_type.get(name, []))
            for name in sorted_types
        ]

        return TasksExecutionTimeResponse(
            timezone=tz_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            task_types=sorted_types,
            series=series,
        )
```

Note: this method does NOT emit a synthetic point for empty `(date, task_name)` cells. That's the intentional gap behaviour described in the design doc.

- [ ] **Step 2: Verify syntax**

Run from `backend/`: `python -c "from app.modules.admin.service import AdminService; print(hasattr(AdminService, 'get_tasks_execution_time'))"`

Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/admin/service.py
git commit -m "feat(admin): aggregate tasks execution-time percentiles"
```

---

## Task 4: Backend router endpoints

**Files:**
- Modify: `backend/app/modules/admin/router.py`

- [ ] **Step 1: Import new schemas**

Add `TasksDailyTrendResponse` and `TasksExecutionTimeResponse` to the existing `from app.modules.admin.schemas import (...)` block (alphabetical order):

```python
from app.modules.admin.schemas import (
    AIUsageDailyTrendResponse,
    BatchRetryRequest,
    BatchRetryResponse,
    DashboardStats,
    JobsDailyTrendResponse,
    JobsTimeScatterResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskRetryResponse,
    TaskStatisticsResponse,
    TasksDailyTrendResponse,
    TasksExecutionTimeResponse,
    WorkerMonitorResponse,
)
```

- [ ] **Step 2: Add two GET routes**

Insert these two route handlers between the existing `get_ai_cost_daily_trend` (line ~67–72 in current file) and `get_worker_status` (line ~75):

```python
@router.get("/tasks/daily-trend", response_model=TasksDailyTrendResponse)
async def get_tasks_daily_trend(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Daily task counts and failure rates per task_name (with Total series)."""
    return await AdminService.get_tasks_daily_trend(db, days=days)


@router.get("/tasks/execution-time", response_model=TasksExecutionTimeResponse)
async def get_tasks_execution_time(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Daily avg / p50 / p95 task execution time per task_name (successful tasks only)."""
    return await AdminService.get_tasks_execution_time(db, days=days)
```

**Important:** Both routes must be declared *before* the existing `@router.get("/tasks/{task_id}", ...)` line (currently at line ~129), otherwise FastAPI will match `daily-trend` and `execution-time` as `task_id` values. Inserting them between the AI cost endpoint and the workers endpoint achieves this.

- [ ] **Step 3: Smoke-verify the FastAPI app boots**

Run from `backend/`:

```bash
uvicorn app.main:app --port 8001 --host 127.0.0.1
```

Wait for `Application startup complete.` then in another shell:

```bash
curl -s http://127.0.0.1:8001/openapi.json | python -c "import json,sys; spec=json.load(sys.stdin); paths=spec['paths']; print('/admin/tasks/daily-trend:', '/admin/tasks/daily-trend' in paths); print('/admin/tasks/execution-time:', '/admin/tasks/execution-time' in paths)"
```

Expected:
```
/admin/tasks/daily-trend: True
/admin/tasks/execution-time: True
```

Stop the server (Ctrl-C).

- [ ] **Step 4: Smoke-verify aggregation queries against the dev DB**

Re-start uvicorn as in step 3, then (replace `$ADMIN_TOKEN` with a valid admin bearer; if the user has no auth handy locally, run the queries directly via psql instead — see fallback below):

```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://127.0.0.1:8001/admin/tasks/daily-trend?days=7" | python -m json.tool | head -40
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://127.0.0.1:8001/admin/tasks/execution-time?days=7" | python -m json.tool | head -40
```

Expected: a JSON response with `timezone`, `startDate`, `endDate`, `taskTypes` array, and `series` array. The `Total` series in daily-trend should have 7 points. Each `series[].points[]` for execution-time has only days with successful samples.

**Fallback if auth is inconvenient:** run the underlying SQL directly via psql to sanity-check counts match what the API returns:

```sql
SELECT (created_at AT TIME ZONE 'Pacific/Auckland')::date AS d,
       task_name,
       count(*) AS total,
       sum(case when status = 'Failed' then 1 else 0 end) AS failed
FROM task_executions
WHERE created_at >= now() - interval '7 days'
GROUP BY 1, 2 ORDER BY 1, 2;
```

If the API output rows match this query for matching `(date, task_name)` pairs, aggregation is correct.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/admin/router.py
git commit -m "feat(admin): expose tasks daily-trend and execution-time routes"
```

---

## Task 5: Frontend response types

**Files:**
- Modify: `frontend/src/features/admin/types.ts`

- [ ] **Step 1: Locate the existing admin types file structure**

Open `frontend/src/features/admin/types.ts` and find where `JobsDailyTrendResponse` is defined. Append the new types at the end of the file (or alongside related types — match the existing organisation pattern).

- [ ] **Step 2: Append types**

```typescript
// ===== Tasks Analytics =====
export interface TasksDailyTrendPoint {
  date: string
  count: number
  failed: number
  failureRate: number | null
}

export interface TasksDailyTrendSeries {
  name: string
  points: TasksDailyTrendPoint[]
}

export interface TasksDailyTrendResponse {
  timezone: string
  startDate: string
  endDate: string
  taskTypes: string[]
  series: TasksDailyTrendSeries[]
}

export interface TasksExecutionTimePoint {
  date: string
  avgMs: number
  p50Ms: number
  p95Ms: number
  sampleCount: number
}

export interface TasksExecutionTimeSeries {
  name: string
  points: TasksExecutionTimePoint[]
}

export interface TasksExecutionTimeResponse {
  timezone: string
  startDate: string
  endDate: string
  taskTypes: string[]
  series: TasksExecutionTimeSeries[]
}
```

- [ ] **Step 3: Verify tsc**

Run from `frontend/`: `npx tsc --noEmit`

Expected: no errors (existing project should be clean; this task only adds exports).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/admin/types.ts
git commit -m "feat(admin): add tasks analytics response types"
```

---

## Task 6: Frontend API client methods

**Files:**
- Modify: `frontend/src/api/admin.ts`

- [ ] **Step 1: Import new response types and add methods**

Update the imports block to include the new types, and add two methods to the `adminApi` object near the other `/admin/...` trend getters:

```typescript
import apiClient from './client'
import type {
  DashboardStats,
  WorkerMonitorResponse,
  TaskListResponse,
  TaskDetailResponse,
  TaskStatisticsResponse,
  BatchRetryRequest,
  BatchRetryResponse,
  TaskRetryResponse,
  AIUsageDailyTrendResponse,
  JobsDailyTrendResponse,
  JobsTimeScatterResponse,
  TasksDailyTrendResponse,
  TasksExecutionTimeResponse,
} from '@/features/admin/types'

export const adminApi = {
  getDashboardStats: () => apiClient.get<DashboardStats>('/admin/dashboard/stats'),
  getJobsDailyTrend: (params?: { days?: number }) =>
    apiClient.get<JobsDailyTrendResponse>('/admin/jobs/daily-trend', { params }),
  getJobsTimeScatter: (params?: { days?: number }) =>
    apiClient.get<JobsTimeScatterResponse>('/admin/jobs/time-scatter', { params }),
  getAITokensDailyTrend: (params?: { days?: number }) =>
    apiClient.get<AIUsageDailyTrendResponse>('/admin/ai/tokens-daily-trend', { params }),
  getAICostDailyTrend: (params?: { days?: number }) =>
    apiClient.get<AIUsageDailyTrendResponse>('/admin/ai/cost-daily-trend', { params }),
  getTasksDailyTrend: (params?: { days?: number }) =>
    apiClient.get<TasksDailyTrendResponse>('/admin/tasks/daily-trend', { params }),
  getTasksExecutionTime: (params?: { days?: number }) =>
    apiClient.get<TasksExecutionTimeResponse>('/admin/tasks/execution-time', { params }),
  // ... existing methods below remain unchanged
```

Note: keep all existing methods after the two new ones. The diff is purely additive.

- [ ] **Step 2: Verify tsc**

Run from `frontend/`: `npx tsc --noEmit`

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/admin.ts
git commit -m "feat(admin): add tasks analytics api client methods"
```

---

## Task 7: Frontend React Query hooks

**Files:**
- Create: `frontend/src/features/admin/hooks/useTasksDailyTrend.ts`
- Create: `frontend/src/features/admin/hooks/useTasksExecutionTime.ts`

- [ ] **Step 1: Create `useTasksDailyTrend.ts`**

```typescript
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useTasksDailyTrend(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'tasks-daily-trend', days],
    queryFn: () => adminApi.getTasksDailyTrend({ days }),
  })
}
```

- [ ] **Step 2: Create `useTasksExecutionTime.ts`**

```typescript
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useTasksExecutionTime(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'tasks-execution-time', days],
    queryFn: () => adminApi.getTasksExecutionTime({ days }),
  })
}
```

- [ ] **Step 3: Verify tsc**

Run from `frontend/`: `npx tsc --noEmit`

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/admin/hooks/useTasksDailyTrend.ts frontend/src/features/admin/hooks/useTasksExecutionTime.ts
git commit -m "feat(admin): add tasks analytics react query hooks"
```

---

## Task 8: Wire tasks card to new route

**Files:**
- Modify: `frontend/src/features/admin/components/DashboardStats.tsx` (lines 69–77 in current file)

- [ ] **Step 1: Add `href` to the tasks card config**

Find the tasks entry in the `cards` array (currently around line 69):

```typescript
  {
    key: 'tasks',
    label: 'Tasks',
    theme: {
      border: 'border-amber-300',
      tint: 'from-amber-100 via-white to-stone-50',
      accent: 'from-amber-700 to-orange-700',
      title: 'text-amber-900',
    },
  },
```

Add `href: '/admin/tasks/chart',` after the `label` line:

```typescript
  {
    key: 'tasks',
    label: 'Tasks',
    href: '/admin/tasks/chart',
    theme: {
      border: 'border-amber-300',
      tint: 'from-amber-100 via-white to-stone-50',
      accent: 'from-amber-700 to-orange-700',
      title: 'text-amber-900',
    },
  },
```

No other changes — the existing `isLinkedCard` logic and `onClick` handler already pick up `href` automatically (see lines 152–162 of current file).

- [ ] **Step 2: Verify tsc**

Run from `frontend/`: `npx tsc --noEmit`

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/admin/components/DashboardStats.tsx
git commit -m "feat(admin): link dashboard tasks card to analytics page"
```

---

## Task 9: Page skeleton + route registration

**Files:**
- Create: `frontend/src/features/admin/pages/AdminTasksChartPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the skeleton page file**

```typescript
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useTasksDailyTrend } from '../hooks/useTasksDailyTrend'
import { useTasksExecutionTime } from '../hooks/useTasksExecutionTime'

const COLORS = [
  '#2563eb',
  '#ea580c',
  '#7c3aed',
  '#059669',
  '#dc2626',
  '#0891b2',
  '#ca8a04',
  '#db2777',
]

function pickTaskColor(name: string, sortedNames: string[]): string {
  const idx = sortedNames.indexOf(name)
  return COLORS[(idx >= 0 ? idx : 0) % COLORS.length]
}

function ChartStateBox({ message }: { message: string }) {
  return (
    <div className="flex h-[24rem] items-center justify-center rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-600">
      {message}
    </div>
  )
}

export default function AdminTasksChartPage() {
  const [countDays, setCountDays] = useState(30)
  const [durationDays, setDurationDays] = useState(30)

  const countQuery = useTasksDailyTrend(countDays)
  const durationQuery = useTasksExecutionTime(durationDays)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tasks Charts</h1>
          <p className="text-sm text-slate-600">
            Daily task volume, failure rate, and execution-time percentiles by task type.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/admin/dashboard">Back</Link>
        </Button>
      </div>

      <Card className="shadow-sm border-slate-200">
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base font-semibold text-slate-900">
                Tasks Volume &amp; Failure Rate
              </CardTitle>
              <p className="mt-1 text-sm text-slate-600">
                {countQuery.data
                  ? `Stacked count by task_name with overall failure rate. ${countQuery.data.startDate} ~ ${countQuery.data.endDate} (${countQuery.data.timezone})`
                  : 'Loading...'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {[7, 30, 60].map((d) => (
                <Button
                  key={d}
                  variant={countDays === d ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setCountDays(d)}
                >
                  {d}D
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {countQuery.isLoading && <ChartStateBox message="Loading chart..." />}
          {!countQuery.isLoading && countQuery.isError && (
            <ChartStateBox message="Failed to load chart data." />
          )}
          {!countQuery.isLoading && !countQuery.isError && (!countQuery.data || countQuery.data.series.length === 0) && (
            <ChartStateBox message="No data." />
          )}
          {/* Chart 1 body added in Task 10 */}
        </CardContent>
      </Card>

      <Card className="shadow-sm border-slate-200">
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base font-semibold text-slate-900">
                Execution Time
              </CardTitle>
              <p className="mt-1 text-sm text-slate-600">
                {durationQuery.data
                  ? `Avg / p50 / p95 of successful tasks by task_name. ${durationQuery.data.startDate} ~ ${durationQuery.data.endDate} (${durationQuery.data.timezone})`
                  : 'Loading...'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {[7, 30, 60].map((d) => (
                <Button
                  key={d}
                  variant={durationDays === d ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setDurationDays(d)}
                >
                  {d}D
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {durationQuery.isLoading && <ChartStateBox message="Loading chart..." />}
          {!durationQuery.isLoading && durationQuery.isError && (
            <ChartStateBox message="Failed to load chart data." />
          )}
          {!durationQuery.isLoading && !durationQuery.isError && (!durationQuery.data || durationQuery.data.series.length === 0) && (
            <ChartStateBox message="No data." />
          )}
          {/* Chart 2 body added in Task 11 */}
        </CardContent>
      </Card>
    </div>
  )
}

```

`COLORS`, `pickTaskColor`, `ChartStateBox` are module-scoped helpers in this file; Tasks 10 and 11 add chart bodies that reference them directly — no re-export needed.

- [ ] **Step 2: Register the route in `App.tsx`**

Find the existing line (around line 31):

```typescript
import AdminJobsChartPage from '@/features/admin/pages/AdminJobsChartPage'
```

Add immediately after:

```typescript
import AdminTasksChartPage from '@/features/admin/pages/AdminTasksChartPage'
```

Find the route group containing (around line 96):

```typescript
<Route path="/admin/jobs/chart" element={<AdminJobsChartPage />} />
<Route path="/admin/ai/charts" element={<AdminAIUsageChartPage />} />
```

Add immediately after:

```typescript
<Route path="/admin/tasks/chart" element={<AdminTasksChartPage />} />
```

- [ ] **Step 3: Verify navigation works (manual smoke)**

Start the frontend dev server: `cd frontend && npm run dev`

Open the admin dashboard, click the Tasks card. Expected: navigates to `/admin/tasks/chart`, both cards show "Loading..." then either real data or "No data." Back button returns to dashboard.

If the backend isn't running, the cards show "Failed to load chart data." — that's acceptable for this skeleton task.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/admin/pages/AdminTasksChartPage.tsx frontend/src/App.tsx
git commit -m "feat(admin): add tasks analytics page skeleton and route"
```

---

## Task 10: Chart 1 — stacked bar/area with failure rate overlay

**Files:**
- Modify: `frontend/src/features/admin/pages/AdminTasksChartPage.tsx`

- [ ] **Step 1: Add Recharts imports**

At the top of the page file, add the import line:

```typescript
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useChartReady } from '@/lib/useChartReady'
import { useMemo } from 'react'
```

Update the existing `useState` import line to add `useMemo` if not yet present (the example above shows `import { useMemo } from 'react'` separately to make the diff explicit — if the file already has `import { useState } from 'react'`, change it to `import { useMemo, useState } from 'react'`).

- [ ] **Step 2: Add state for legend toggles and per-type rate visibility**

Inside `AdminTasksChartPage`, just after the `useTasksExecutionTime` call:

```typescript
  const [countHidden, setCountHidden] = useState<Record<string, boolean>>({})
  const [showPerTypeFailureRate, setShowPerTypeFailureRate] = useState(false)
  const [countChartRef, countChartReady] = useChartReady<HTMLDivElement>()

  const countData = countQuery.data
  const countMode: 'bar' | 'area' = countDays <= 7 ? 'bar' : 'area'

  const totalSeries = useMemo(
    () => countData?.series.find((s) => s.name === 'Total'),
    [countData],
  )
  const taskSeries = useMemo(
    () => countData?.series.filter((s) => s.name !== 'Total') ?? [],
    [countData],
  )
  const sortedTaskNames = useMemo(
    () => [...(countData?.taskTypes ?? [])].sort(),
    [countData],
  )

  // Row per date: { date, shortDate, <task_name>: count, ..., overallFailureRate, <task_name>__rate: ratePct }
  const countChartRows = useMemo(() => {
    if (!countData || !totalSeries) return []
    return totalSeries.points.map((totalPoint, idx) => {
      const row: Record<string, string | number | null> = {
        date: totalPoint.date,
        shortDate: totalPoint.date.slice(5),
        overallFailureRate:
          totalPoint.failureRate === null ? null : totalPoint.failureRate * 100,
      }
      for (const s of taskSeries) {
        const p = s.points[idx]
        row[s.name] = p?.count ?? 0
        row[`${s.name}__rate`] =
          p?.failureRate === null || p?.failureRate === undefined ? null : p.failureRate * 100
      }
      return row
    })
  }, [countData, totalSeries, taskSeries])

  const toggleTaskInCountChart = (name: string) => {
    setCountHidden((prev) => ({ ...prev, [name]: !prev[name] }))
  }
```

- [ ] **Step 3: Add the chart body inside the first `<CardContent>` (replace the `{/* Chart 1 body added in Task 10 */}` comment)**

```typescript
          {!countQuery.isLoading && !countQuery.isError && countData && totalSeries && countChartRows.length > 0 && (
            <div className="space-y-4">
              <div
                ref={countChartRef}
                className="h-[24rem] rounded-2xl border border-slate-200 bg-slate-50/70 p-2 sm:p-4"
              >
                {countChartReady && (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={countChartRows}
                      margin={{ top: 12, right: 20, bottom: 6, left: 0 }}
                    >
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="shortDate"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#64748b', fontSize: 11 }}
                      />
                      <YAxis
                        yAxisId="left"
                        allowDecimals={false}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        domain={[0, 'auto']}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                        tickFormatter={(v: number) => `${Math.round(v)}%`}
                      />
                      <Tooltip
                        formatter={(value: number | string, name: string) => {
                          if (typeof name === 'string' && name.endsWith(' %')) {
                            return [
                              value === null ? '—' : `${Number(value).toFixed(1)}%`,
                              name,
                            ]
                          }
                          return [value, name]
                        }}
                      />
                      <Legend wrapperStyle={{ display: 'none' }} />

                      {countMode === 'bar'
                        ? taskSeries.map((s) =>
                            countHidden[s.name] ? null : (
                              <Bar
                                key={`bar-${s.name}`}
                                yAxisId="left"
                                dataKey={s.name}
                                stackId="count"
                                fill={pickTaskColor(s.name, sortedTaskNames)}
                                name={s.name}
                              />
                            ),
                          )
                        : taskSeries.map((s) =>
                            countHidden[s.name] ? null : (
                              <Area
                                key={`area-${s.name}`}
                                yAxisId="left"
                                type="monotone"
                                dataKey={s.name}
                                stackId="count"
                                stroke={pickTaskColor(s.name, sortedTaskNames)}
                                fill={pickTaskColor(s.name, sortedTaskNames)}
                                fillOpacity={0.6}
                                name={s.name}
                              />
                            ),
                          )}

                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="overallFailureRate"
                        stroke="#dc2626"
                        strokeWidth={2.5}
                        strokeDasharray="4 2"
                        dot={false}
                        connectNulls={false}
                        name="Overall failure rate %"
                      />

                      {showPerTypeFailureRate &&
                        taskSeries.map((s) =>
                          countHidden[s.name] ? null : (
                            <Line
                              key={`rate-${s.name}`}
                              yAxisId="right"
                              type="monotone"
                              dataKey={`${s.name}__rate`}
                              stroke={pickTaskColor(s.name, sortedTaskNames)}
                              strokeWidth={1.5}
                              strokeDasharray="4 2"
                              dot={false}
                              connectNulls={false}
                              name={`${s.name} %`}
                            />
                          ),
                        )}
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {taskSeries.map((s) => {
                  const hidden = !!countHidden[s.name]
                  const color = pickTaskColor(s.name, sortedTaskNames)
                  return (
                    <button
                      key={s.name}
                      onClick={() => toggleTaskInCountChart(s.name)}
                      className={`inline-flex items-center gap-2 rounded border px-2 py-1 text-xs ${
                        hidden ? 'border-slate-200 text-slate-400' : 'border-slate-300 text-slate-700'
                      }`}
                    >
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                      <span>{s.name}</span>
                    </button>
                  )
                })}
                <button
                  onClick={() => setShowPerTypeFailureRate((v) => !v)}
                  className={`inline-flex items-center gap-2 rounded border px-2 py-1 text-xs ${
                    showPerTypeFailureRate
                      ? 'border-rose-300 text-rose-700 bg-rose-50'
                      : 'border-slate-300 text-slate-700'
                  }`}
                >
                  <span className="h-2.5 w-0.5" style={{ borderTop: '2px dashed #dc2626', width: '12px' }} />
                  <span>{showPerTypeFailureRate ? 'Hide' : 'Show'} per-type failure rate</span>
                </button>
              </div>
            </div>
          )}
```

- [ ] **Step 4: Verify tsc and visual rendering**

Run `npx tsc --noEmit` in `frontend/`. Expected: no errors.

Then `npm run dev`, navigate to `/admin/tasks/chart`. Expected:
- 7D shows stacked bars; switching to 30D / 60D switches to stacked areas.
- Dashed red line for overall failure rate is visible on the right Y axis (percentages).
- Clicking task-name legend buttons hides/shows that series in bars/areas AND its per-type rate line (when the latter is enabled).
- The "Show per-type failure rate" toggle reveals additional dashed lines coloured to match each task.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/admin/pages/AdminTasksChartPage.tsx
git commit -m "feat(admin): render tasks volume chart with failure rate overlay"
```

---

## Task 11: Chart 2 — execution time lines with metric switch

**Files:**
- Modify: `frontend/src/features/admin/pages/AdminTasksChartPage.tsx`

- [ ] **Step 1: Add state for duration chart**

Add inside `AdminTasksChartPage` near the other state declarations:

```typescript
  const [durationMetric, setDurationMetric] = useState<'avgMs' | 'p50Ms' | 'p95Ms'>('p50Ms')
  const [durationScale, setDurationScale] = useState<'linear' | 'log'>('linear')
  const [durationHidden, setDurationHidden] = useState<Record<string, boolean>>({})
  const [durationChartRef, durationChartReady] = useChartReady<HTMLDivElement>()

  const durationData = durationQuery.data
  const sortedDurationTaskNames = useMemo(
    () => [...(durationData?.taskTypes ?? [])].sort(),
    [durationData],
  )

  // Build one row per date with one key per task_name carrying the selected metric.
  // Days where a task_name had zero successful samples become null on that key.
  const { durationChartRows, durationUnit, durationUnitDivisor } = useMemo(() => {
    if (!durationData) {
      return { durationChartRows: [], durationUnit: 'ms', durationUnitDivisor: 1 }
    }
    // Low-sample handling (v1 fallback per spec): skip points with sampleCount < 3.
    // The downstream gap (lookup miss -> null) naturally breaks the line at those days.
    const MIN_SAMPLE = 3
    // Union of all dates appearing in any series, sorted.
    const allDates = new Set<string>()
    for (const s of durationData.series) {
      for (const p of s.points) allDates.add(p.date)
    }
    const dates = Array.from(allDates).sort()

    // Per-(date, task_name) lookup for fast row construction.
    const lookup = new Map<string, Map<string, number>>()
    for (const s of durationData.series) {
      const inner = new Map<string, number>()
      for (const p of s.points) {
        if (p.sampleCount < MIN_SAMPLE) continue
        inner.set(p.date, p[durationMetric])
      }
      lookup.set(s.name, inner)
    }

    // Decide unit based on max value seen across visible, sufficiently-sampled series.
    let maxMs = 0
    for (const s of durationData.series) {
      if (durationHidden[s.name]) continue
      for (const p of s.points) {
        if (p.sampleCount < MIN_SAMPLE) continue
        if (p[durationMetric] > maxMs) maxMs = p[durationMetric]
      }
    }
    let unit: 'ms' | 's' | 'm' = 'ms'
    let divisor = 1
    if (maxMs >= 3_600_000) {
      unit = 'm'
      divisor = 60_000
    } else if (maxMs >= 60_000) {
      unit = 's'
      divisor = 1_000
    }

    const rows = dates.map((date) => {
      const row: Record<string, string | number | null> = {
        date,
        shortDate: date.slice(5),
      }
      for (const name of sortedDurationTaskNames) {
        const v = lookup.get(name)?.get(date)
        row[name] = v === undefined ? null : v / divisor
      }
      return row
    })
    return { durationChartRows: rows, durationUnit: unit, durationUnitDivisor: divisor }
  }, [durationData, durationMetric, durationHidden, sortedDurationTaskNames])

  const toggleTaskInDurationChart = (name: string) => {
    setDurationHidden((prev) => ({ ...prev, [name]: !prev[name] }))
  }
```

- [ ] **Step 2: Insert metric / scale switches into the second card header**

Find the second `<Card>` block in the page. Replace its existing header range-button group with this richer version that adds metric and scale switches alongside the days buttons:

```typescript
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 rounded border border-slate-300 p-0.5">
                {(['avgMs', 'p50Ms', 'p95Ms'] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setDurationMetric(m)}
                    className={`rounded px-2 py-1 text-xs ${
                      durationMetric === m
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    {m === 'avgMs' ? 'avg' : m === 'p50Ms' ? 'p50' : 'p95'}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setDurationScale((s) => (s === 'linear' ? 'log' : 'linear'))}
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
              >
                {durationScale === 'linear' ? 'linear' : 'log'}
              </button>
              {[7, 30, 60].map((d) => (
                <Button
                  key={d}
                  variant={durationDays === d ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setDurationDays(d)}
                >
                  {d}D
                </Button>
              ))}
            </div>
```

- [ ] **Step 3: Add the chart body (replace `{/* Chart 2 body added in Task 11 */}`)**

```typescript
          {!durationQuery.isLoading && !durationQuery.isError && durationData && durationChartRows.length > 0 && (
            <div className="space-y-4">
              <div
                ref={durationChartRef}
                className="h-[24rem] rounded-2xl border border-slate-200 bg-slate-50/70 p-2 sm:p-4"
              >
                {durationChartReady && (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={durationChartRows}
                      margin={{ top: 12, right: 20, bottom: 6, left: 0 }}
                    >
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="shortDate"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#64748b', fontSize: 11 }}
                      />
                      <YAxis
                        scale={durationScale}
                        domain={durationScale === 'log' ? [0.01, 'auto'] : [0, 'auto']}
                        allowDataOverflow={durationScale === 'log'}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                        tickFormatter={(v: number) => `${v.toFixed(v < 10 ? 1 : 0)} ${durationUnit}`}
                      />
                      <Tooltip
                        formatter={(value: number | null, name: string) => [
                          value === null ? '—' : `${Number(value).toFixed(2)} ${durationUnit}`,
                          name,
                        ]}
                      />
                      <Legend wrapperStyle={{ display: 'none' }} />

                      {sortedDurationTaskNames.map((name) =>
                        durationHidden[name] ? null : (
                          <Line
                            key={`duration-${name}`}
                            type="monotone"
                            dataKey={name}
                            stroke={pickTaskColor(name, sortedDurationTaskNames)}
                            strokeWidth={2}
                            dot={false}
                            connectNulls={false}
                            name={name}
                          />
                        ),
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                {sortedDurationTaskNames.map((name) => {
                  const hidden = !!durationHidden[name]
                  const color = pickTaskColor(name, sortedDurationTaskNames)
                  return (
                    <button
                      key={`duration-legend-${name}`}
                      onClick={() => toggleTaskInDurationChart(name)}
                      className={`inline-flex items-center gap-2 rounded border px-2 py-1 text-xs ${
                        hidden ? 'border-slate-200 text-slate-400' : 'border-slate-300 text-slate-700'
                      }`}
                    >
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                      <span>{name}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
```

Note: `durationUnitDivisor` is computed inside the `useMemo` but only used internally to convert values before they enter the row data, so it doesn't need to be referenced again in this block. The `ComposedChart` is used for both charts purely for consistency; for the duration chart only `<Line>` series are rendered.

- [ ] **Step 4: Verify tsc and visual rendering**

`npx tsc --noEmit` from `frontend/`. Expected: no errors.

`npm run dev`, navigate to `/admin/tasks/chart`:
- Chart 2 shows one line per task type, defaulting to p50, linear scale.
- Switching avg/p50/p95 re-renders without refetch.
- Switching linear/log re-axes; values that are zero (e.g., a task type with no samples that day) gap out the line.
- Y-axis label unit (ms/s/m) auto-adjusts to the magnitude of visible data.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/admin/pages/AdminTasksChartPage.tsx
git commit -m "feat(admin): render tasks execution-time chart with metric/scale switches"
```

---

## Task 12: End-to-end smoke verification

**Files:** none (manual)

- [ ] **Step 1: Restart both services from clean state**

In one terminal:

```bash
cd backend && uvicorn app.main:app --reload --port 8001
```

In another:

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Run through the user journey**

1. Open the frontend, sign in as an admin user.
2. Navigate to admin dashboard. Tasks card should now have hover lift + cursor pointer (matches Jobs/Tokens cards).
3. Click the Tasks card. URL should become `/admin/tasks/chart` and both chart cards should render.
4. **Chart 1:**
   - Confirm 7D shows stacked bars and 30D/60D shows stacked areas.
   - Confirm the dashed red overall-failure-rate line is on the right axis showing percentages.
   - Toggle a task-name legend chip — that type disappears from the stack AND its per-type rate line (if visible) disappears together.
   - Toggle "Show per-type failure rate" — dashed coloured lines for each visible task appear/disappear.
5. **Chart 2:**
   - Confirm a line per task type renders, defaulting to p50.
   - Switch avg / p50 / p95 — lines redraw immediately.
   - Switch linear / log — Y axis changes shape; very-fast tasks become more visible in log mode.
   - Y-axis tick units auto-switch between ms / s / m depending on magnitude.
   - Toggle task-name legend chip — that line disappears.
6. Back button returns to `/admin/dashboard`.

- [ ] **Step 3: Sanity-check empty-state branches**

- Open browser devtools → Network → temporarily block the two new API calls (right-click → Block request URL). Reload. Expect "Failed to load chart data." in both cards.
- Unblock; if the local DB has no `task_executions` rows for some date ranges, the empty-state message should be `"No data."` (otherwise data renders).

- [ ] **Step 4: Final commit (if any cleanup was needed)**

If you made any tweaks in Steps 2/3 above (e.g., wording, tooltip formatting), commit them:

```bash
git add -A
git commit -m "chore(admin): tasks analytics page smoke-test polish"
```

If no cleanup was needed, skip this step.

---

## Done criteria

- `/admin/tasks/chart` route registered and renders both charts.
- Dashboard tasks card is a clickable link.
- Backend endpoints `/admin/tasks/daily-trend` and `/admin/tasks/execution-time` return well-formed JSON for `days ∈ {7, 30, 60}`.
- Chart 1: stacked bar (7D) / area (30D, 60D), dashed overall failure-rate line, legend toggle per type, optional per-type rate lines.
- Chart 2: line per task type, avg/p50/p95 switch, linear/log switch, ms/s/m unit auto-pick, legend toggle.
- No TypeScript errors. No Python import errors. App starts clean.
