import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useJobsDailyTrend } from '../hooks/useJobsDailyTrend'
import { useJobsTimeScatter } from '../hooks/useJobsTimeScatter'
import type {
  JobsDailyTrendSeries,
  JobsTimeScatterPoint,
} from '../types'

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

function pickColor(index: number) {
  return COLORS[index % COLORS.length]
}

function pickSeriesColor(name: string, seriesNames: string[]) {
  const index = seriesNames.indexOf(name)
  return pickColor(index >= 0 ? index : 0)
}

// Returns true if a YYYY-MM-DD string falls on Saturday or Sunday
function isWeekend(dateStr: string): boolean {
  const day = new Date(dateStr + 'T12:00:00Z').getUTCDay()
  return day === 0 || day === 6
}

// Returns true if a YYYY-MM-DD string falls on Monday
function isMonday(dateStr: string): boolean {
  return new Date(dateStr + 'T12:00:00Z').getUTCDay() === 1
}
// Computes explicit XAxis ticks for the scatter chart.
// Interval: 3h for 1-day range, 6h for 3-day, 12h for 7-day.
// Every tick at offset 0 from a midnight is guaranteed to be in midnightSet.
function computeScatterTicks(
  startTs: number,
  endTs: number,
  timezone: string,
  days: number,
): { ticks: number[]; midnightSet: Set<number> } {
  const intervalHours = days <= 1 ? 3 : days <= 3 ? 6 : 12
  const hourMs = 3600 * 1000
  // Scan a slightly extended range so even the day before startTs has a midnight seed
  const scanStart = Math.floor(startTs / hourMs) * hourMs - 26 * hourMs
  const seenDates = new Set<string>()
  const dateFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone })
  const seedMidnights: number[] = []

  const timeFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  for (let t = scanStart; t <= endTs + hourMs; t += hourMs) {
    const parts = timeFormatter.formatToParts(t)
    const hour = parts.find((p) => p.type === 'hour')?.value
    const minute = parts.find((p) => p.type === 'minute')?.value

    if (hour === '00' && minute === '00') {
      const dateStr = dateFormatter.format(t)
      if (!seenDates.has(dateStr)) {
        seenDates.add(dateStr)
        seedMidnights.push(t)
      }
    }
  }

  const tickSet = new Set<number>()
  const midnightSet = new Set<number>()

  for (const midnight of seedMidnights) {
    for (let i = 0; i < 24 / intervalHours; i++) {
      const t = midnight + i * intervalHours * hourMs
      if (t >= startTs && t <= endTs) {
        tickSet.add(t)
        if (i === 0) midnightSet.add(t)
      }
    }
  }

  return {
    ticks: Array.from(tickSet).sort((a, b) => a - b),
    midnightSet,
  }
}

interface TrendTooltipProps {
  active?: boolean
  payload?: Array<{
    value?: number
    name?: string
    color?: string
    dataKey?: string
  }>
  label?: string
}

function TrendTooltip({ active, payload, label }: TrendTooltipProps) {
  if (!active || !payload?.length) return null

  const rows = [...payload].sort((left, right) => {
    const leftIsTotal = left.name === 'Total' ? -1 : 0
    const rightIsTotal = right.name === 'Total' ? -1 : 0
    if (leftIsTotal !== rightIsTotal) return leftIsTotal - rightIsTotal
    return Number(right.value ?? 0) - Number(left.value ?? 0)
  })

  return (
    <div className="min-w-44 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-xl">
      <div className="text-sm font-semibold text-slate-950">{label}</div>
      <div className="mt-2 space-y-1 text-xs text-slate-600">
        {rows.map((entry) => (
          <div key={entry.name} className="flex items-center justify-between gap-6">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
              {entry.name}
            </span>
            <span className="font-medium text-slate-900">{entry.value ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

interface ScatterTooltipProps {
  active?: boolean
  payload?: Array<{
    payload?: {
      bucketLabel: string
      source: string
      count: number
    }
    color?: string
  }>
}

function ScatterPointTooltip({ active, payload }: ScatterTooltipProps) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null

  return (
    <div className="min-w-44 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-xl">
      <div className="text-sm font-semibold text-slate-950">{point.source}</div>
      <div className="mt-1 text-xs text-slate-600">{point.bucketLabel}</div>
      <div className="mt-2 text-xs text-slate-600">
        Count: <span className="font-medium text-slate-900">{point.count}</span>
      </div>
    </div>
  )
}

function formatTooltipDateTime(timestamp: number, timezone: string) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .format(timestamp)
    .replace(',', '')
}

function formatRangeDateTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function renderScatterPoint(props: {
  cx?: number
  cy?: number
  fill?: string
}) {
  return (
    <circle
      cx={props.cx}
      cy={props.cy}
      r={3}
      fill={props.fill}
      fillOpacity={0.8}
      stroke="#ffffff"
      strokeWidth={0.5}
    />
  )
}

function ChartStateBox({ message }: { message: string }) {
  return (
    <div className="flex h-[24rem] items-center justify-center rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-600">
      {message}
    </div>
  )
}

export default function AdminJobsChartPage() {
  const [trendDays, setTrendDays] = useState(30)
  const [scatterDays, setScatterDays] = useState(7)
  const trendQuery = useJobsDailyTrend(trendDays)
  const scatterQuery = useJobsTimeScatter(scatterDays)
  const data = trendQuery.data
  const scatterData = scatterQuery.data
  const [hiddenSeries, setHiddenSeries] = useState<Record<string, boolean>>({})

  const series: JobsDailyTrendSeries[] = data?.series ?? []
  // Merge sources from both charts so the same source always maps to the same color index
  const sourceColorNames = useMemo(() => {
    const names = new Set<string>()

    for (const source of data?.sources ?? []) {
      names.add(source)
    }

    for (const source of scatterData?.sources ?? []) {
      names.add(source)
    }

    return Array.from(names).sort()
  }, [data?.sources, scatterData?.sources])

  const chartData = useMemo(() => {
    const totalSeries = series.find((item) => item.name === 'Total')
    const dates = totalSeries?.points.map((point) => point.date) ?? []

    return dates.map((date, index) => {
      const row: Record<string, string | number> = {
        date,
        shortDate: date.slice(5),
      }

      for (const item of series) {
        row[item.name] = item.points[index]?.count ?? 0
      }

      return row
    })
  }, [series])

  // Chart 1: map shortDate → full date string for weekend/monday detection
  const dateMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const d of chartData) map[d.shortDate as string] = d.date as string
    return map
  }, [chartData])

  // Chart 1: shortDate values that fall on Monday (used for vertical reference lines)
  const mondayDates = useMemo(
    () => chartData.filter((d) => isMonday(d.date as string)).map((d) => d.shortDate as string),
    [chartData],
  )

  // Chart 1: explicit tick list so weekend labels are never dropped by Recharts auto-skip.
  // 7D → every day; 30D → Mon + Sat (shows week boundaries + weekend start);
  // 60D → Mon only (keeps label density reasonable).
  const trendTicks = useMemo(() => {
    if (trendDays <= 7) {
      return chartData.map((d) => d.shortDate as string)
    }
    return chartData
      .filter((d) => {
        const full = d.date as string
        const day = new Date(full + 'T12:00:00Z').getUTCDay()
        return trendDays <= 30 ? day === 1 || day === 6 : day === 1
      })
      .map((d) => d.shortDate as string)
  }, [chartData, trendDays])

  // Chart 2: explicit ticks, midnight set, and domain derived from scatter time range.
  // Domain is based on the query range (not dataMin/dataMax) so midnight ticks that
  // fall in hours with no data are never clipped as out-of-domain.
  const { scatterTicks, scatterMidnightSet, scatterDomain } = useMemo(() => {
    if (!scatterData) return {
      scatterTicks: [],
      scatterMidnightSet: new Set<number>(),
      scatterDomain: ['dataMin', 'dataMax'] as [string, string],
    }
    const startTs = new Date(scatterData.startDateTime).getTime()
    const endTs = new Date(scatterData.endDateTime).getTime()
    const { ticks, midnightSet } = computeScatterTicks(startTs, endTs, scatterData.timezone, scatterDays)

    let visibleTicks: number[]
    if (scatterDays <= 1) {
      // 1D: every 3h tick for readable time distribution
      visibleTicks = ticks
    } else if (scatterDays <= 3) {
      // 3D: midnight + noon only (2 ticks/day)
      const noonSet = new Set(
        Array.from(midnightSet).map((midnight) => midnight + 12 * 3600 * 1000),
      )
      visibleTicks = ticks.filter((t) => midnightSet.has(t) || noonSet.has(t))
    } else {
      // 7D: only midnight
      visibleTicks = Array.from(midnightSet)
    }

    return {
      scatterTicks: visibleTicks.sort((a, b) => a - b),
      scatterMidnightSet: midnightSet,
      scatterDomain: [startTs, endTs] as [number, number],
    }
  }, [scatterData, scatterDays])

  const scatterPoints = useMemo(() => {
    const timezone = scatterData?.timezone ?? 'UTC'
    return (scatterData?.points ?? []).map((point: JobsTimeScatterPoint) => {
      const timestamp = new Date(point.bucketStart).getTime()
      return {
        ...point,
        timestamp,
        bucketLabel: formatTooltipDateTime(timestamp, timezone),
      }
    })
  }, [scatterData])

  const scatterSeries = useMemo(() => {
    const grouped = new Map<string, Array<JobsTimeScatterPoint & { timestamp: number; bucketLabel: string }>>()

    for (const point of scatterPoints) {
      if (hiddenSeries[point.source]) continue
      const current = grouped.get(point.source) ?? []
      current.push(point)
      grouped.set(point.source, current)
    }

    return Array.from(grouped.entries())
  }, [scatterPoints, hiddenSeries])

  const toggleSeries = (name: string) => {
    setHiddenSeries((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Jobs Charts</h1>
          <p className="text-sm text-slate-600">Trend and hourly scatter views in app local time.</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/admin/dashboard">Back</Link>
        </Button>
      </div>

      <Card className="shadow-sm border-slate-200">
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base font-semibold text-slate-900">Jobs Daily Trend</CardTitle>
              <p className="mt-1 text-sm text-slate-600">
                {data
                  ? `Daily new jobs by source. ${data.startDate} ~ ${data.endDate} (${data.timezone})`
                  : 'Loading...'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={trendDays === 7 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendDays(7)}
              >
                7D
              </Button>
              <Button
                variant={trendDays === 30 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendDays(30)}
              >
                30D
              </Button>
              <Button
                variant={trendDays === 60 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTrendDays(60)}
              >
                60D
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {trendQuery.isLoading && <ChartStateBox message="Loading chart..." />}
          {!trendQuery.isLoading && trendQuery.isError && (
            <ChartStateBox message="Failed to load chart data." />
          )}
          {!trendQuery.isLoading && !trendQuery.isError && (!data || series.length === 0) && (
            <ChartStateBox message="No data." />
          )}
          {!trendQuery.isLoading && !trendQuery.isError && data && series.length > 0 && (
            <div className="space-y-4">
              <div className="h-[24rem] rounded-2xl border border-slate-200 bg-slate-50/70 p-2 sm:p-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={chartData}
                    margin={{ top: 12, right: 20, bottom: 6, left: 0 }}
                  >
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="shortDate"
                      axisLine={false}
                      tickLine={false}
                      ticks={trendTicks}
                      tick={(props: { x?: string | number; y?: string | number; payload?: { value: string } }) => {
                        const { x = 0, y = 0, payload } = props
                        if (!payload) return <g />
                        const fullDate = dateMap[payload.value]
                        const weekend = fullDate ? isWeekend(fullDate) : false
                        return (
                          <text
                            x={x}
                            y={y}
                            dy={12}
                            textAnchor="middle"
                            fill={weekend ? '#f97316' : '#64748b'}
                            fontWeight={weekend ? 600 : 400}
                            fontSize={11}
                          >
                            {payload.value}
                          </text>
                        )
                      }}
                    />
                    <YAxis
                      allowDecimals={false}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                    />
                    <Tooltip content={<TrendTooltip />} />

                    {/* Vertical line at each Monday marking the start of the week */}
                    {mondayDates.map((date) => (
                      <ReferenceLine
                        key={`monday-${date}`}
                        x={date}
                        stroke="#cbd5e1"
                        strokeDasharray="3 3"
                        strokeWidth={1}
                      />
                    ))}

                    {series.map((s: JobsDailyTrendSeries) => {
                      if (hiddenSeries[s.name]) return null
                      const isTotal = s.name === 'Total'
                      const stroke = isTotal ? '#111827' : pickSeriesColor(s.name, sourceColorNames)

                      return (
                        <Line
                          key={s.name}
                          type="monotone"
                          dataKey={s.name}
                          name={s.name}
                          stroke={stroke}
                          strokeWidth={isTotal ? 3 : 2}
                          dot={false}
                          activeDot={{ r: isTotal ? 5 : 4 }}
                        />
                      )
                    })}
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="flex flex-wrap gap-2">
                {series.map((s: JobsDailyTrendSeries) => {
                  const isTotal = s.name === 'Total'
                  const hidden = !!hiddenSeries[s.name]
                  const color = isTotal ? '#111827' : pickSeriesColor(s.name, sourceColorNames)
                  return (
                    <button
                      key={s.name}
                      onClick={() => toggleSeries(s.name)}
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
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="shadow-sm border-slate-200">
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base font-semibold text-slate-900">Jobs Time Scatter</CardTitle>
              <p className="mt-1 text-sm text-slate-600">
                {scatterData
                  ? `Hourly local-time job counts by source. ${formatRangeDateTime(
                      scatterData.startDateTime,
                      scatterData.timezone
                    )} ~ ${formatRangeDateTime(scatterData.endDateTime, scatterData.timezone)} (${scatterData.timezone})`
                  : 'Loading...'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={scatterDays === 1 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setScatterDays(1)}
              >
                1D
              </Button>
              <Button
                variant={scatterDays === 3 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setScatterDays(3)}
              >
                3D
              </Button>
              <Button
                variant={scatterDays === 7 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setScatterDays(7)}
              >
                7D
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {scatterQuery.isLoading && <ChartStateBox message="Loading scatter chart..." />}
          {!scatterQuery.isLoading && scatterQuery.isError && (
            <ChartStateBox message="Failed to load scatter data." />
          )}
          {!scatterQuery.isLoading && !scatterQuery.isError && (!scatterData || scatterPoints.length === 0) && (
            <ChartStateBox message="No scatter data." />
          )}
          {!scatterQuery.isLoading && !scatterQuery.isError && scatterData && scatterPoints.length > 0 && (
            <div className="space-y-4">
              <div className="h-[24rem] rounded-2xl border border-slate-200 bg-slate-50/70 p-2 sm:p-4">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 12, right: 20, bottom: 6, left: 0 }}>
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                    <XAxis
                      type="number"
                      dataKey="timestamp"
                      domain={scatterDomain}
                      scale="time"
                      axisLine={false}
                      tickLine={false}
                      ticks={scatterTicks}
                      height={36}
                      minTickGap={1}
                      tick={(props: { x?: string | number; y?: string | number; payload?: { value: number } }) => {
                        const { x = 0, y = 0, payload } = props
                        if (!payload) return <g />
                        const ts = payload.value
                        const isMidnight = scatterMidnightSet.has(ts)
                        const label = isMidnight
                          ? new Intl.DateTimeFormat('en-US', {
                              timeZone: scatterData.timezone,
                              month: '2-digit',
                              day: '2-digit',
                            }).format(ts)
                          : new Intl.DateTimeFormat('en-US', {
                              timeZone: scatterData.timezone,
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: false,
                            }).format(ts)
                        return (
                          <text
                            x={x}
                            y={y}
                            dy={12}
                            textAnchor="middle"
                            fill={isMidnight ? '#f97316' : '#64748b'}
                            fontWeight={isMidnight ? 600 : 400}
                            fontSize={11}
                          >
                            {label}
                          </text>
                        )
                      }}
                    />
                    <YAxis
                      type="number"
                      dataKey="count"
                      allowDecimals={false}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                    />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<ScatterPointTooltip />} />

                    {/* Vertical line at each day boundary (midnight in chart timezone) */}
                    {Array.from(scatterMidnightSet).map((ts) => (
                      <ReferenceLine
                        key={`midnight-${ts}`}
                        x={ts}
                        stroke="#cbd5e1"
                        strokeDasharray="3 3"
                        strokeWidth={1}
                      />
                    ))}

                    {scatterSeries.map(([source, points]) => (
                      <Scatter
                        key={source}
                        name={source}
                        data={points}
                        fill={pickSeriesColor(source, sourceColorNames)}
                        line={false}
                        shape={renderScatterPoint}
                      />
                    ))}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>

              <div className="flex flex-wrap gap-2">
                {(scatterData.sources ?? []).map((source) => {
                  const hidden = !!hiddenSeries[source]
                  const color = pickSeriesColor(source, sourceColorNames)
                  return (
                    <button
                      key={`scatter-${source}`}
                      onClick={() => toggleSeries(source)}
                      className={`inline-flex items-center gap-2 rounded border px-2 py-1 text-xs ${
                        hidden ? 'border-slate-200 text-slate-400' : 'border-slate-300 text-slate-700'
                      }`}
                    >
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                      <span>{source}</span>
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
