import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, BriefcaseBusiness, Clock3, Layers3, Send, Target, Trophy, Users } from 'lucide-react'

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

export function ApplicationActivityCard({
  data,
  isLoading,
  hasError,
}: ApplicationActivityCardProps) {
  if (isLoading) {
    return <Skeleton className="h-[34rem] w-full rounded-3xl" />
  }

  const maxValue = Math.max(1, ...data.points.map((point) => Math.max(point.addedCount, point.appliedCount)))

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
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-400" />
                Added
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
                Applied
              </div>
            </div>
          </div>

          <div className="mt-5">
            <div className="flex items-stretch gap-3">
              <div className="flex h-44 w-8 flex-col justify-between text-[11px] text-slate-400">
                <span>{maxValue}</span>
                <span>{Math.max(0, Math.round(maxValue / 2))}</span>
                <span>0</span>
              </div>
              <div
                className="grid h-44 flex-1 gap-2"
                style={{ gridTemplateColumns: `repeat(${data.points.length}, minmax(0, 1fr))` }}
              >
                {data.points.map((point) => {
                  const addedHeight = `${(point.addedCount / maxValue) * 100}%`
                  const appliedHeight = `${(point.appliedCount / maxValue) * 100}%`

                  return (
                    <div key={point.dateKey} className="flex min-w-0 flex-col items-center justify-end gap-2">
                      <div className="relative flex h-full w-full items-end justify-center gap-1 rounded-2xl border border-slate-200/80 bg-white/80 px-1.5 pb-2 pt-4">
                        <div
                          className="w-full rounded-full bg-slate-400/80"
                          style={{ height: addedHeight }}
                          title={`${point.label}: ${point.addedCount} added`}
                        />
                        <div
                          className="w-full rounded-full bg-indigo-500"
                          style={{ height: appliedHeight }}
                          title={`${point.label}: ${point.appliedCount} applied`}
                        />
                      </div>
                      <div className="text-[11px] text-slate-500">{point.shortLabel}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium text-slate-500">Outcomes</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricCard
              label="Phone Screens"
              value={data.outcomes.phoneScreens.toString()}
              helper="Applications currently in phone screen"
              icon={Users}
            />
            <MetricCard
              label="Interviews"
              value={data.outcomes.interviewing.toString()}
              helper="Applications currently interviewing"
              icon={Target}
            />
            <MetricCard
              label="Offers"
              value={data.outcomes.offers.toString()}
              helper="Applications marked as offer"
              icon={Trophy}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
