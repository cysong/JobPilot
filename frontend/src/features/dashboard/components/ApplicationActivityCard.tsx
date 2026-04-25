import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, BriefcaseBusiness, Clock3, Layers3, Send, Target, Trophy, Users } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardApplicationActivity } from '@/features/dashboard/types'

interface ApplicationActivityCardProps {
  data: DashboardApplicationActivity
  isLoading: boolean
  hasError: boolean
}

interface MetricCardProps {
  label: string
  value: string
  helper: string
  icon: ComponentType<{ className?: string }>
}

interface ActivityTooltipProps {
  active?: boolean
  payload?: Array<{
    value?: number
    name?: string
    color?: string
    dataKey?: string
  }>
  label?: string
}

const ADDED_COLOR = '#94a3b8'
const ADDED_ACTIVE_COLOR = '#64748b'
const APPLIED_COLOR = '#6366f1'
const APPLIED_ACTIVE_COLOR = '#4338ca'

function MetricCard({ label, value, helper, icon: Icon }: MetricCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-slate-500">{label}</div>
        <Icon className="h-4 w-4 text-slate-400" />
      </div>
      <div className="mt-3 text-2xl font-bold text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{helper}</div>
    </div>
  )
}

function ActivityTooltip({ active, payload, label }: ActivityTooltipProps) {
  if (!active || !payload?.length) return null

  const addedValue = payload.find((entry) => entry.dataKey === 'addedCount')?.value ?? 0
  const appliedValue = payload.find((entry) => entry.dataKey === 'appliedCount')?.value ?? 0

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-xl">
      <div className="text-sm font-semibold text-slate-950">{label}</div>
      <div className="mt-2 space-y-1 text-xs text-slate-600">
        <div className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: ADDED_COLOR }} />
            Added
          </span>
          <span className="font-medium text-slate-900">{addedValue}</span>
        </div>
        <div className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: APPLIED_COLOR }} />
            Applied
          </span>
          <span className="font-medium text-slate-900">{appliedValue}</span>
        </div>
      </div>
    </div>
  )
}

export function ApplicationActivityCard({
  data,
  isLoading,
  hasError,
}: ApplicationActivityCardProps) {
  if (isLoading) {
    return <Skeleton className="h-[34rem] w-full rounded-3xl" />
  }

  return (
    <Card className="rounded-3xl border-slate-200 shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-slate-500">Applications</div>
          <CardTitle className="text-xl text-slate-950">Application Activity</CardTitle>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/applications">
            Open Applications
            <ArrowUpRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {hasError ? (
          <div className="rounded-2xl border border-dashed border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load activity data. Open the full applications page to retry.
          </div>
        ) : null}

        <div className="space-y-3">
          <div className="text-sm font-medium text-slate-500">Workflow</div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Added"
              value={data.workflow.addedCount.toString()}
              helper={`Added in the last ${data.periodDays} days`}
              icon={BriefcaseBusiness}
            />
            <MetricCard
              label="Applied"
              value={data.workflow.appliedCount.toString()}
              helper={`Applied in the last ${data.periodDays} days`}
              icon={Send}
            />
            <MetricCard
              label="Backlog"
              value={data.workflow.backlogCount.toString()}
              helper="Added but not yet marked applied"
              icon={Layers3}
            />
            <MetricCard
              label="Avg time to apply"
              value={data.workflow.averageDaysToApplyLabel}
              helper="Average days from Added to Applied"
              icon={Clock3}
            />
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-slate-500">Daily volume</div>
              <div className="text-base font-semibold text-slate-950">
                Added vs Applied over the last {data.periodDays} days
              </div>
            </div>
            <div className="text-xs text-slate-500">Hover bars to compare daily volume.</div>
          </div>

          <div className="mt-5 h-64 rounded-2xl border border-slate-200/80 bg-white/85 px-2 py-3 sm:h-72 sm:px-4">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart
                data={data.points}
                margin={{ top: 12, right: 8, bottom: 6, left: -20 }}
                barCategoryGap="24%"
              >
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="shortLabel"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#64748b', fontSize: 11 }}
                  minTickGap={16}
                />
                <YAxis
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                />
                <Tooltip cursor={{ fill: 'rgba(99, 102, 241, 0.06)' }} content={<ActivityTooltip />} />
                <Legend
                  verticalAlign="top"
                  align="right"
                  iconType="circle"
                  wrapperStyle={{ paddingBottom: 12, fontSize: '12px', color: '#64748b' }}
                />
                <Bar
                  dataKey="addedCount"
                  name="Added"
                  fill={ADDED_COLOR}
                  activeBar={{ fill: ADDED_ACTIVE_COLOR }}
                  radius={[8, 8, 0, 0]}
                  maxBarSize={18}
                >
                  {data.points.map((point) => (
                    <Cell
                      key={`${point.dateKey}-added`}
                      fill={point.addedCount > 0 ? ADDED_COLOR : '#cbd5e1'}
                    />
                  ))}
                </Bar>
                <Bar
                  dataKey="appliedCount"
                  name="Applied"
                  fill={APPLIED_COLOR}
                  activeBar={{ fill: APPLIED_ACTIVE_COLOR }}
                  radius={[8, 8, 0, 0]}
                  maxBarSize={18}
                >
                  {data.points.map((point) => (
                    <Cell
                      key={`${point.dateKey}-applied`}
                      fill={point.appliedCount > 0 ? APPLIED_COLOR : '#c7d2fe'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium text-slate-500">Outcomes</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricCard
              label="Phone Screens"
              value={data.outcomes.phoneScreens.toString()}
              helper="Applications that ever reached phone screen"
              icon={Users}
            />
            <MetricCard
              label="Interviews"
              value={data.outcomes.interviewing.toString()}
              helper="Applications that ever reached interviewing"
              icon={Target}
            />
            <MetricCard
              label="Offers"
              value={data.outcomes.offers.toString()}
              helper="Applications that ever received an offer"
              icon={Trophy}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
