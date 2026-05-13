import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
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
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useChartReady } from '@/lib/useChartReady'
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

  // Chart 1 state
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

  // Chart 2 state
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
  const { durationChartRows, durationUnit } = useMemo(() => {
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

              <div className="space-y-2">
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
                </div>
                <div>
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
            </div>
          )}
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
        </CardContent>
      </Card>
    </div>
  )
}
