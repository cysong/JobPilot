import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useJobsDailyTrend } from '../hooks/useJobsDailyTrend'
import type { JobsDailyTrendResponse, JobsDailyTrendSeries } from '../types'

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

export default function AdminJobsChartPage() {
  const [days, setDays] = useState(30)
  const query = useJobsDailyTrend(days)
  const data = query.data as unknown as JobsDailyTrendResponse | undefined
  const [hiddenSeries, setHiddenSeries] = useState<Record<string, boolean>>({})

  const series: JobsDailyTrendSeries[] = data?.series ?? []
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
                      tick={{ fill: '#64748b', fontSize: 11 }}
                      minTickGap={24}
                    />
                    <YAxis
                      allowDecimals={false}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                    />
                    <Tooltip content={<TrendTooltip />} />

                    {series.map((s: JobsDailyTrendSeries, idx: number) => {
                      if (hiddenSeries[s.name]) return null
                      const isTotal = s.name === 'Total'
                      const stroke = isTotal ? '#111827' : pickColor(idx)

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
