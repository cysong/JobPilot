import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowUpRight, CheckCircle2, Clock3, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/utils/cn'
import type { DashboardPriorityAction } from '@/features/dashboard/types'

interface PriorityActionCardProps {
  action: DashboardPriorityAction | null
  isLoading: boolean
}

const toneConfig = {
  default: {
    icon: Sparkles,
    iconClass: 'bg-indigo-100 text-indigo-700',
    borderClass: 'border-slate-200',
  },
  success: {
    icon: CheckCircle2,
    iconClass: 'bg-emerald-100 text-emerald-700',
    borderClass: 'border-emerald-200',
  },
  warning: {
    icon: Clock3,
    iconClass: 'bg-amber-100 text-amber-700',
    borderClass: 'border-amber-200',
  },
  danger: {
    icon: AlertTriangle,
    iconClass: 'bg-red-100 text-red-700',
    borderClass: 'border-red-200',
  },
} satisfies Record<NonNullable<DashboardPriorityAction['tone']>, {
  icon: typeof Sparkles
  iconClass: string
  borderClass: string
}>

export function PriorityActionCard({ action, isLoading }: PriorityActionCardProps) {
  if (isLoading) {
    return <Skeleton className="h-52 w-full rounded-3xl" />
  }

  if (!action) {
    return null
  }

  const config = toneConfig[action.tone]
  const Icon = config.icon

  return (
    <Card className={cn('rounded-3xl border shadow-sm', config.borderClass)}>
      <CardHeader className="pb-4">
        <div className="flex items-center gap-3">
          <div className={cn('flex h-11 w-11 items-center justify-center rounded-2xl', config.iconClass)}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-medium text-slate-500">Priority Action</div>
            <CardTitle className="text-xl text-slate-950">{action.title}</CardTitle>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <p className="max-w-2xl text-sm leading-6 text-slate-600">{action.description}</p>
        <Button asChild className="bg-slate-950 text-white hover:bg-slate-800">
          {action.external ? (
            <a href={action.href} target="_blank" rel="noopener noreferrer">
              {action.ctaLabel}
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </a>
          ) : (
            <Link to={action.href}>
              {action.ctaLabel}
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </Link>
          )}
        </Button>
      </CardContent>
    </Card>
  )
}
