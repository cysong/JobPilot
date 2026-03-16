import { Link } from 'react-router-dom'

import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/utils/cn'
import type { DashboardMetric } from '@/features/dashboard/types'

interface DashboardMetricCardsProps {
  metrics: DashboardMetric[]
  isLoading: boolean
}

const toneClasses: Record<NonNullable<DashboardMetric['tone']>, string> = {
  default: 'border-slate-200',
  success: 'border-emerald-200 bg-emerald-50/40',
  warning: 'border-amber-200 bg-amber-50/40',
}

export function DashboardMetricCards({ metrics, isLoading }: DashboardMetricCardsProps) {
  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-32 w-full rounded-2xl" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <Link key={metric.label} to={metric.href}>
          <Card
            className={cn(
              'h-full rounded-2xl border transition-all hover:-translate-y-0.5 hover:shadow-md',
              toneClasses[metric.tone || 'default']
            )}
          >
            <CardContent className="space-y-3 p-5">
              <div className="text-sm font-medium text-slate-500">{metric.label}</div>
              <div className="text-3xl font-bold tracking-tight text-slate-950">{metric.value}</div>
              <div className="text-sm text-slate-600">{metric.helper}</div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}
