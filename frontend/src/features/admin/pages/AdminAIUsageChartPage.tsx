import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
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
import { useAICostDailyTrend } from '../hooks/useAICostDailyTrend'
import { useAITokensDailyTrend } from '../hooks/useAITokensDailyTrend'
import type { AIUsageDailyTrendResponse, AIUsageDailyTrendSeries } from '../types'

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

function formatCompactNumber(value: number) {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: value >= 100_000 ? 0 : 1,
  }).format(value)
}

function formatCurrency(value: number) {
  if (value >= 1000) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value)
  }

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 1 ? 4 : 2,
    maximumFractionDigits: value < 1 ? 4 : 2,
  }).format(value)
}

function ChartStateBox({ message }: { message: string }) {
  return (
    <div className="flex h-[24rem] items-center justify-center rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-600">
      {message}
    </div>
  )
}

interface TrendTooltipProps {
  active?: boolean
  payload?: Array<{
    value?: number
    name?: string
    color?: string
  }>
  label?: string
  formatter: (value: number) => string
}

function TrendTooltip({ active, payload, label, formatter }: TrendTooltipProps) {
  if (!active || !payload?.length) return null

  const rows = [...payload].sort((left, right) => {
    const leftIsTotal = left.name === 'Total' ? -1 : 0
    const rightIsTotal = right.name === 'Total' ? -1 : 0
    if (leftIsTotal !== rightIsTotal) return leftIsTotal - rightIsTotal
    return Number(right.value ?? 0) - Number(left.value ?? 0)
  })

  return (
    <div className="min-w-48 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-xl">
      <div className="text-sm font-semibold text-slate-950">{label}</div>
      <div className="mt-2 space-y-1 text-xs text-slate-600">
        {rows.map((entry) => (
          <div key={entry.name} className="flex items-center justify-between gap-6">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
              {entry.name}
            </span>
            <span className="font-medium text-slate-900">{formatter(Number(entry.value ?? 0))}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function buildChartData(series: AIUsageDailyTrendSeries[]) {
  const totalSeries = series.find((item) => item.name === 'Total')
  const dates = totalSeries?.points.map((point) => point.date) ?? []

  return dates.map((date, index) => {
    const row: Record<string, string | number> = {
      date,
      shortDate: date.slice(5),
    }

    for (const item of series) {
      row[item.name] = item.points[index]?.value ?? 0
    }

    return row
  })
}

function AITrendCard({
  id,
  title,
  subtitle,
  days,
  setDays,
  data,
  isLoading,
  hiddenSeries,
  toggleSeries,
  formatter,
  yTickFormatter,
}: {
  id: string
  title: string
  subtitle: string
  days: number
  setDays: (days: number) => void
  data: AIUsageDailyTrendResponse | undefined
  isLoading: boolean
  hiddenSeries: Record<string, boolean>
  toggleSeries: (name: string) => void
  formatter: (value: number) => string
  yTickFormatter: (value: number) => string
}) {
  const series = data?.series ?? []
  const chartData = useMemo(() => buildChartData(series), [series])
  const modelColorNames = useMemo(() => [...(data?.models ?? [])].sort(), [data?.models])

  return (
    <Card id={id} className="scroll-mt-24 border-slate-200 shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-base font-semibold text-slate-900">{title}</CardTitle>
            <p className="mt-1 text-sm text-slate-600">
              {data ? `${subtitle} ${data.startDate} ~ ${data.endDate} (${data.timezone})` : 'Loading...'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant={days === 7 ? 'default' : 'outline'} size="sm" onClick={() => setDays(7)}>7D</Button>
            <Button variant={days === 30 ? 'default' : 'outline'} size="sm" onClick={() => setDays(30)}>30D</Button>
            <Button variant={days === 60 ? 'default' : 'outline'} size="sm" onClick={() => setDays(60)}>60D</Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && <ChartStateBox message="Loading chart..." />}
        {!isLoading && (!data || series.length === 0) && <ChartStateBox message="No data." />}
        {!isLoading && data && series.length > 0 && (
          <div className="space-y-4">
            <div className="h-[24rem] rounded-2xl border border-slate-200 bg-slate-50/70 p-2 sm:p-4">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <LineChart data={chartData} margin={{ top: 12, right: 20, bottom: 6, left: 0 }}>
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="shortDate"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    minTickGap={24}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    tickFormatter={yTickFormatter}
                  />
                  <Tooltip content={<TrendTooltip formatter={formatter} />} />
                  {series.map((item) => {
                    if (hiddenSeries[item.name]) return null
                    const isTotal = item.name === 'Total'
                    const stroke = isTotal ? '#111827' : pickSeriesColor(item.name, modelColorNames)

                    return (
                      <Line
                        key={item.name}
                        type="monotone"
                        dataKey={item.name}
                        name={item.name}
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
              {series.map((item) => {
                const isTotal = item.name === 'Total'
                const hidden = !!hiddenSeries[item.name]
                const color = isTotal ? '#111827' : pickSeriesColor(item.name, modelColorNames)
                return (
                  <button
                    key={`${id}-${item.name}`}
                    onClick={() => toggleSeries(item.name)}
                    className={`inline-flex items-center gap-2 rounded border px-2 py-1 text-xs ${
                      hidden ? 'border-slate-200 text-slate-400' : 'border-slate-300 text-slate-700'
                    }`}
                  >
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                    <span>{item.name}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function AdminAIUsageChartPage() {
  const location = useLocation()
  const [days, setDays] = useState(30)
  const tokensQuery = useAITokensDailyTrend(days)
  const costQuery = useAICostDailyTrend(days)
  const tokensData = tokensQuery.data as unknown as AIUsageDailyTrendResponse | undefined
  const costData = costQuery.data as unknown as AIUsageDailyTrendResponse | undefined
  const [hiddenSeries, setHiddenSeries] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!location.hash) return

    const elementId = location.hash.slice(1)
    const scrollToAnchor = () => {
      const element = document.getElementById(elementId)
      if (!element) return
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }

    const frameId = window.requestAnimationFrame(scrollToAnchor)
    return () => window.cancelAnimationFrame(frameId)
  }, [location.hash])

  const toggleSeries = (name: string) => {
    setHiddenSeries((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">AI Usage Charts</h1>
          <p className="text-sm text-slate-600">Daily tokens and estimated cost trends by model.</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/admin/dashboard">Back</Link>
        </Button>
      </div>

      <AITrendCard
        id="tokens"
        title="Daily Tokens"
        subtitle="Daily token consumption totals and per-model series."
        days={days}
        setDays={setDays}
        data={tokensData}
        isLoading={tokensQuery.isLoading}
        hiddenSeries={hiddenSeries}
        toggleSeries={toggleSeries}
        formatter={formatCompactNumber}
        yTickFormatter={formatCompactNumber}
      />

      <AITrendCard
        id="cost"
        title="Daily Estimated Cost"
        subtitle="Daily estimated USD cost totals and per-model series."
        days={days}
        setDays={setDays}
        data={costData}
        isLoading={costQuery.isLoading}
        hiddenSeries={hiddenSeries}
        toggleSeries={toggleSeries}
        formatter={formatCurrency}
        yTickFormatter={(value) => (value >= 1 ? formatCurrency(value) : `$${value.toFixed(2)}`)}
      />
    </div>
  )
}
