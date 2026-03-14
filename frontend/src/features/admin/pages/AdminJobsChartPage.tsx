import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useJobsDailyTrend } from '../hooks/useJobsDailyTrend'
import type { JobsDailyTrendResponse, JobsDailyTrendSeries } from '../types'

const CHART_WIDTH = 980
const CHART_HEIGHT = 360
const PAD = { top: 20, right: 24, bottom: 42, left: 46 }
const COLORS = [
  '#0f766e',
  '#1d4ed8',
  '#be123c',
  '#7c3aed',
  '#ca8a04',
  '#0e7490',
  '#9333ea',
  '#16a34a',
]

function pickColor(index: number) {
  return COLORS[index % COLORS.length]
}

export default function AdminJobsChartPage() {
  const [days, setDays] = useState(30)
  const query = useJobsDailyTrend(days)
  const data = query.data as unknown as JobsDailyTrendResponse | undefined
  const [hiddenSeries, setHiddenSeries] = useState<Record<string, boolean>>({})

  const series: JobsDailyTrendSeries[] = data?.series ?? []
  const dates = series[0]?.points.map((p: { date: string }) => p.date) ?? []

  const maxCount = useMemo(() => {
    const visible = series.filter((s: JobsDailyTrendSeries) => !hiddenSeries[s.name])
    const values = visible.flatMap((s: JobsDailyTrendSeries) => s.points.map((p: { count: number }) => p.count))
    return Math.max(1, ...values, 0)
  }, [series, hiddenSeries])

  const plotWidth = CHART_WIDTH - PAD.left - PAD.right
  const plotHeight = CHART_HEIGHT - PAD.top - PAD.bottom

  const x = (idx: number) => {
    if (dates.length <= 1) return PAD.left
    return PAD.left + (idx / (dates.length - 1)) * plotWidth
  }
  const y = (count: number) => PAD.top + plotHeight - (count / maxCount) * plotHeight

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((r) => Math.round(maxCount * r))
  const xTickIndexes = dates.length <= 8
    ? dates.map((_: string, i: number) => i)
    : [0, Math.floor(dates.length * 0.25), Math.floor(dates.length * 0.5), Math.floor(dates.length * 0.75), dates.length - 1]

  const toggleSeries = (name: string) => {
    setHiddenSeries((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Jobs Daily Trend</h1>
          <p className="text-sm text-slate-600">
            Last {days} days daily new jobs by source ({data?.timezone ?? 'Loading timezone...'}).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/dashboard">Back</Link>
          </Button>
          <Button variant={days === 7 ? 'default' : 'outline'} size="sm" onClick={() => setDays(7)}>7D</Button>
          <Button variant={days === 30 ? 'default' : 'outline'} size="sm" onClick={() => setDays(30)}>30D</Button>
          <Button variant={days === 60 ? 'default' : 'outline'} size="sm" onClick={() => setDays(60)}>60D</Button>
        </div>
      </div>

      <Card className="shadow-sm border-slate-200">
        <CardHeader>
          <CardTitle className="text-sm font-medium text-slate-700">
            {data ? `${data.startDate} ~ ${data.endDate}` : 'Loading...'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading && <div className="text-sm text-slate-600">Loading chart...</div>}
          {!query.isLoading && (!data || series.length === 0) && (
            <div className="text-sm text-slate-600">No data.</div>
          )}
          {!query.isLoading && data && series.length > 0 && (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <svg width={CHART_WIDTH} height={CHART_HEIGHT} role="img" aria-label="Jobs daily trend chart">
                  <rect x={PAD.left} y={PAD.top} width={plotWidth} height={plotHeight} fill="transparent" />

                  {yTicks.map((tick) => (
                    <g key={`y-${tick}`}>
                      <line
                        x1={PAD.left}
                        y1={y(tick)}
                        x2={PAD.left + plotWidth}
                        y2={y(tick)}
                        stroke="#e2e8f0"
                        strokeWidth="1"
                      />
                      <text x={PAD.left - 8} y={y(tick) + 4} textAnchor="end" fontSize="11" fill="#64748b">
                        {tick}
                      </text>
                    </g>
                  ))}

                  {xTickIndexes.map((idx: number) => (
                    <g key={`x-${idx}`}>
                      <line
                        x1={x(idx)}
                        y1={PAD.top}
                        x2={x(idx)}
                        y2={PAD.top + plotHeight}
                        stroke="#f1f5f9"
                        strokeWidth="1"
                      />
                      <text
                        x={x(idx)}
                        y={PAD.top + plotHeight + 18}
                        textAnchor="middle"
                        fontSize="11"
                        fill="#64748b"
                      >
                        {dates[idx]?.slice(5) ?? ''}
                      </text>
                    </g>
                  ))}

                  {series.map((s: JobsDailyTrendSeries, idx: number) => {
                    if (hiddenSeries[s.name]) return null
                    const points = s.points.map((p: { count: number }, i: number) => `${x(i)},${y(p.count)}`).join(' ')
                    const isTotal = s.name === 'Total'
                    const stroke = isTotal ? '#111827' : pickColor(idx)

                    return (
                      <g key={s.name}>
                        <polyline
                          fill="none"
                          stroke={stroke}
                          strokeWidth={isTotal ? 3 : 2}
                          points={points}
                        />
                      </g>
                    )
                  })}

                  <text x={PAD.left} y={PAD.top - 6} fontSize="11" fill="#64748b">Jobs</text>
                </svg>
              </div>

              <div className="flex flex-wrap gap-2">
                {series.map((s: JobsDailyTrendSeries, idx: number) => {
                  const isTotal = s.name === 'Total'
                  const hidden = !!hiddenSeries[s.name]
                  const color = isTotal ? '#111827' : pickColor(idx)
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
    </div>
  )
}
