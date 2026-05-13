# Tasks Analytics Page — Design

> Created 2026-05-13. Owner: Anson. Status: approved (brainstorm), pending implementation plan.

## Goal

Give admins a trend view of background task health: how many tasks run per day, how many fail, and how long they take — broken down by task type. The current `tasks` card on the admin dashboard shows totals only, with no link target.

This page is the analytical counterpart to `TaskMonitorPage`, which remains the operational list/monitor view. Job count and failure-rate visualization shares one chart; execution-time trend lives in a second chart.

## Non-goals

- No CSV export, alerting, or threshold configuration in v1.
- No cross-cut by worker / user; only `task_name` × date.
- No changes to `TaskMonitorPage`; this is a sibling page, not a replacement.

## Entry point

- Modify `frontend/src/features/admin/components/DashboardStats.tsx` so the `tasks` card config gets `href: '/admin/tasks/chart'`. This automatically wires up the same hover lift, focus ring, and click navigation already used by the `jobs`, `aiTokens`, and `aiCost` cards.
- No new icon, no extra link inside the card body — the whole card becomes clickable, matching existing UX.

## Routing

- New route: `/admin/tasks/chart` → `AdminTasksChartPage`.
- Register alongside the existing `/admin/jobs/chart` and `/admin/ai/charts` routes.
- `TaskMonitorPage` route is unchanged.

## Data contracts (backend → frontend)

Two new aggregation endpoints on the admin router, mirroring the shape of `useJobsDailyTrend` so the frontend reuses the same color/series patterns.

### `GET /admin/tasks/daily-trend?days=7|30|60`

```json
{
  "startDate": "2026-04-13",
  "endDate": "2026-05-13",
  "timezone": "Pacific/Auckland",
  "taskTypes": ["fetch_jobs", "match_jobs", "generate_application"],
  "series": [
    {
      "name": "fetch_jobs",
      "points": [
        { "date": "2026-04-13", "count": 42, "failed": 3, "failureRate": 0.071 }
      ]
    },
    {
      "name": "Total",
      "points": [
        { "date": "2026-04-13", "count": 180, "failed": 9, "failureRate": 0.05 }
      ]
    }
  ]
}
```

- `count` = all task rows created that day for that `task_name`, regardless of status.
- `failed` = subset where `status = 'Failed'`.
- `failureRate` = `failed / count`, or `null` when `count = 0` (frontend uses `connectNulls={false}` to break the line).
- `Total` series sums across all task types.
- Days bucketed in the user's app timezone (`Pacific/Auckland`), matching the jobs trend endpoint.

### `GET /admin/tasks/execution-time?days=7|30|60`

```json
{
  "startDate": "2026-04-13",
  "endDate": "2026-05-13",
  "timezone": "Pacific/Auckland",
  "taskTypes": ["match_jobs", "generate_application"],
  "series": [
    {
      "name": "match_jobs",
      "points": [
        { "date": "2026-04-13", "avgMs": 12300, "p50Ms": 9800, "p95Ms": 28000, "sampleCount": 17 }
      ]
    }
  ]
}
```

- Only `status = 'Success'` rows contribute to execution-time stats (failed tasks have unreliable durations).
- `avgMs`, `p50Ms`, `p95Ms` computed in SQL via `percentile_cont` (Postgres) on `execution_time_ms`.
- `sampleCount` exposed for the frontend "low-sample" rendering rule (see Chart 2 below).
- A `(date, task_name)` cell with zero successful samples is omitted from that series' points (frontend breaks the line at that gap).
- No `Total` series for execution time — averaging duration across heterogeneous task types is meaningless.

## Chart 1 — Count + Failure Rate

Single `ComposedChart` with left Y (count) and right Y (failure %), stacked by `task_name`.

### Modes

- **7D**: stacked `<Bar>` per day. Each bar segment = one task type's count.
- **30D / 60D**: auto-switch to stacked `<Area>` (same `stackId`). Computed via `chartMode = days <= 7 ? 'bar' : 'area'` in `useMemo`. Keeps long-range trend readable when 60 bars would compress to slivers.

### Failure-rate overlay

- All failure-rate lines render as `<Line yAxisId="right">` with `connectNulls={false}` and `strokeDasharray="4 2"` (dashed). Dashing disambiguates rate lines from any solid color in the stacked bars/areas underneath.
- **Overall failure rate** (the `Total` series in the response): strokeWidth 2.5, color `#dc2626`, **visible by default**.
- **Per task-name failure rate**: strokeWidth 1.5, color shared with that type's bar/area segment (so eye can map a rate line back to its stack color). **Hidden by default** to avoid clutter.
- Right Y axis: domain `[0, 'auto']`, tick formatter `${(v*100).toFixed(0)}%`.

### Legend

Two-row control under the chart:

1. **Task type row**: one button per `task_name` (same pattern as Jobs page legend). Click toggles that type's bar/area segment AND its per-type failure-rate line together (single source of truth — avoids three-state confusion).
2. **Failure rate row**: a small standalone toggle button `Show per-type failure rate` (off by default). When off, only the Overall line shows. When on, currently-visible task types each get their failure-rate line.

**Visibility rule for a per-type failure-rate line**: rendered iff `taskTypeVisible(name) === true` AND `showPerTypeFailureRate === true`. Hiding a task type via row 1 also hides its rate line, regardless of row 2. The Overall line is independent of both toggles and is always shown.

This keeps the default view simple (stacked counts + one red overall % line) while letting power users drill in.

### Range buttons

`7D` / `30D` / `60D` in the card header, matching Jobs chart layout exactly.

### Color rules

- Task-type colors come from the existing `COLORS` palette in `AdminJobsChartPage.tsx` (or hoisted to a shared util — see Code structure below).
- Assignment: sort `taskTypes` alphabetically once per response, index into the palette. Stable across both charts in this page so a task type has the same color in Chart 1 and Chart 2.
- `Total` failure-rate line always `#dc2626` (red, distinct from any task color).
- No `brand_color` lookup — task types don't have brand identity like job sources.

## Chart 2 — Execution Time

`LineChart` with one line per visible `task_name`.

### Metric switch

- Header buttons: `avg / p50 / p95`. Default **p50** (robust to long-tail outliers and CPU spikes).
- Switching the metric re-renders lines from the same data — no refetch.

### Y axis

- **Unit auto-selection** from the chart's max value across visible series:
  - max < 60_000 ms → axis in `ms`
  - max < 3_600_000 ms → axis in `s`
  - else → `m`
- The unit chosen drives both tick formatting and tooltip formatting (consistent within one render).
- **Scale toggle** in card header: `linear / log`, default `linear`. Log helps when one task type is seconds-scale and another is minutes-scale.

### Low-sample handling

- When `sampleCount < 3` for a `(date, task_name)`, that point is rendered at 30% opacity (still visible, but de-emphasized). Implementation: split each task's points into two arrays (low/high sample) and render as two `<Line>` components per task, only the high-sample line in the legend.
- This is a v1 simplification; if it adds too much code complexity at implementation time, fall back to "skip points with sampleCount < 3" and reassess later.

### Legend

- Task-type toggles only, same button style as Chart 1.
- **Filter state does NOT sync with Chart 1.** Each chart has its own `hiddenSeries` state. Cross-chart sync sounds tidy but tangles state and makes "hide this from just one chart" impossible. Keeping them independent matches how Jobs page treats its two charts.

### Range buttons

`7D` / `30D` / `60D`.

## Frontend file layout

```
frontend/src/features/admin/
├── pages/
│   └── AdminTasksChartPage.tsx       (new)
├── hooks/
│   ├── useTasksDailyTrend.ts          (new)
│   └── useTasksExecutionTime.ts       (new)
├── components/                        (new files only if page > 600 lines)
│   ├── TasksCountChart.tsx            (extracted later if needed)
│   └── TasksDurationChart.tsx         (extracted later if needed)
└── types.ts                           (append TasksDailyTrendResponse, TasksExecutionTimeResponse)
```

Start as a single page file modeled on `AdminJobsChartPage.tsx`. Extract subcomponents only if the file grows past ~600 lines — splitting prematurely just adds prop-threading boilerplate.

### Reused primitives

From `AdminJobsChartPage.tsx`:

- `ChartStateBox` (loading / error / empty state)
- `useChartReady` ResponsiveContainer wrapper
- Tooltip visual style (rounded white card, color dot + label + value)
- Legend button styles
- Range button group pattern

If duplication starts to bite, hoist these to `frontend/src/features/admin/components/charts/` in a follow-up — but not in this change.

## Backend file layout

```
backend/app/modules/admin/
├── router.py            (register two new GET routes)
├── service.py           (add get_tasks_daily_trend, get_tasks_execution_time)
└── schemas.py           (add response models)
```

- SQL aggregation uses the same `tasks` table read paths already used by `list_tasks`.
- Timezone handling reuses whatever the existing jobs trend service does — do not invent a new pattern.
- Percentiles: prefer `percentile_cont(0.5) WITHIN GROUP (ORDER BY execution_time_ms)` in raw SQL via SQLAlchemy `text()` if the ORM path is awkward. Keep the query in a single statement per endpoint.

## Open considerations (resolve at implementation time, not now)

- **Per-type failure-rate line visibility persistence**: should we remember user's toggle across reloads? v1 says no (local state only).
- **Caching**: React Query default cache TTL is fine; no need for custom invalidation.
- **Loading skeleton**: reuse `ChartStateBox` plain text for v1; design fancier skeleton only if it bothers us during use.

## Risks

1. **Stacked area at 60D with many task types** can become muddy if 8+ types exist. Mitigation: legend toggles let users hide noisy types. If we end up with >8 task types in practice, revisit with a "Top N + Other" rollup.
2. **Per-type failure-rate lines + stacked colors can be confusing** even when only some are visible. Mitigation: failure-rate lines are dashed (`strokeDasharray="4 2"`) — this disambiguates them from any solid color reference and from the bar/area fills below.
3. **Percentile computation on a hot table** may be slower than count-based trends. Mitigation: limit `days` to the supported range buttons (max 60), index on `(created_at, task_name, status)` if not present.
