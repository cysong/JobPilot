import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/utils/cn'
import { useNavigate } from 'react-router-dom'
import type { DashboardStats, FloatMetricCount, MetricCount, TaskMetric } from '../types'

interface Props {
  data: DashboardStats | undefined
  isLoading: boolean
  onRefresh?: () => void
}

const cards = [
  {
    key: 'users',
    label: 'Users',
    theme: {
      border: 'border-slate-300',
      tint: 'from-slate-100 via-white to-slate-50',
      accent: 'from-slate-700 to-slate-600',
      title: 'text-slate-800',
    },
  },
  {
    key: 'jobs',
    label: 'Jobs',
    theme: {
      border: 'border-blue-300',
      tint: 'from-blue-100 via-white to-slate-50',
      accent: 'from-blue-800 to-blue-600',
      title: 'text-blue-900',
    },
  },
  {
    key: 'matches',
    label: 'Matches',
    theme: {
      border: 'border-indigo-300',
      tint: 'from-indigo-100 via-white to-slate-50',
      accent: 'from-indigo-800 to-violet-700',
      title: 'text-indigo-900',
    },
  },
  {
    key: 'applications',
    label: 'Applications',
    theme: {
      border: 'border-emerald-300',
      tint: 'from-emerald-100 via-white to-teal-50',
      accent: 'from-emerald-800 to-teal-700',
      title: 'text-emerald-900',
    },
  },
  {
    key: 'tasks',
    label: 'Tasks',
    theme: {
      border: 'border-amber-300',
      tint: 'from-amber-100 via-white to-stone-50',
      accent: 'from-amber-700 to-orange-700',
      title: 'text-amber-900',
    },
  },
  {
    key: 'aiTokens',
    label: 'Tokens',
    theme: {
      border: 'border-cyan-300',
      tint: 'from-cyan-100 via-white to-slate-50',
      accent: 'from-cyan-800 to-sky-700',
      title: 'text-cyan-900',
    },
  },
  {
    key: 'aiCost',
    label: 'Est. Cost',
    theme: {
      border: 'border-rose-300',
      tint: 'from-rose-100 via-white to-stone-50',
      accent: 'from-rose-800 to-pink-700',
      title: 'text-rose-900',
    },
  },
] as const

type CardKey = (typeof cards)[number]['key']
type DashboardMetricItem = MetricCount | TaskMetric | FloatMetricCount | undefined

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

function formatMetricValue(key: CardKey, item: DashboardMetricItem) {
  if (!item) return '0'
  if (key === 'aiTokens') return formatCompactNumber(item.total)
  if (key === 'aiCost') return formatCurrency(item.total)
  return item.total.toLocaleString('en-US')
}

function formatTodayDelta(key: CardKey, item: DashboardMetricItem) {
  if (!item) return ''
  if (key === 'aiTokens') return `+${formatCompactNumber(item.todayNew)} today`
  if (key === 'aiCost') return `+${formatCurrency(item.todayNew)} today`
  return `+${item.todayNew.toLocaleString('en-US')} today`
}

export function DashboardStats({ data, isLoading }: Props) {
  const navigate = useNavigate()

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => {
        const item = data?.[card.key]
        const taskItem = card.key === 'tasks' ? (item as TaskMetric | undefined) : undefined
        const isJobsCard = card.key === 'jobs'
        return (
          <Card
            key={card.key}
            className={cn(
              'relative overflow-hidden border shadow-sm transition-all',
              card.theme.border,
              `bg-gradient-to-br ${card.theme.tint}`,
              isJobsCard && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-md hover:ring-2 hover:ring-blue-200 focus-within:ring-2 focus-within:ring-blue-200'
            )}
            onClick={isJobsCard ? () => navigate('/admin/jobs/chart') : undefined}
          >
            <CardHeader className="pb-2">
              <CardTitle className={cn('text-sm font-medium', card.theme.title)}>{card.label}</CardTitle>
              <div className={cn('mt-2 h-0.5 w-12 rounded-full bg-gradient-to-r', card.theme.accent)} />
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className={cn('text-3xl font-bold text-slate-900', isLoading && 'animate-pulse')}>
                  {isLoading ? '...' : formatMetricValue(card.key, item)}
                </span>
                <span className="text-sm text-emerald-600">
                  {isLoading ? '' : formatTodayDelta(card.key, item)}
                </span>
              </div>
              {card.key === 'tasks' && (
                <div className="mt-2 flex gap-4 text-xs text-slate-600">
                  <span>Running: {isLoading ? '...' : taskItem?.running ?? 0}</span>
                  <span>Failed: {isLoading ? '...' : taskItem?.failed ?? 0}</span>
                </div>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
