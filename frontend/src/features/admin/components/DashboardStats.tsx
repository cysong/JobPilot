import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/utils/cn'
import { useNavigate } from 'react-router-dom'
import type { DashboardStats } from '../types'

interface Props {
  data: DashboardStats | undefined
  isLoading: boolean
  onRefresh?: () => void
}

const cards = [
  { key: 'users', label: 'Users' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'matches', label: 'Matches' },
  { key: 'applications', label: 'Applications' },
  { key: 'tasks', label: 'Tasks' },
] as const

export function DashboardStats({ data, isLoading }: Props) {
  const navigate = useNavigate()

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((card) => {
        const item = (data as any)?.[card.key]
        const isJobsCard = card.key === 'jobs'
        return (
          <Card
            key={card.key}
            className={cn(
              'shadow-sm border-slate-200',
              isJobsCard && 'cursor-pointer hover:border-indigo-300 hover:shadow-md transition-all'
            )}
            onClick={isJobsCard ? () => navigate('/admin/jobs/chart') : undefined}
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">{card.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className={cn('text-3xl font-bold text-slate-900', isLoading && 'animate-pulse')}>
                  {isLoading ? '—' : item?.total ?? 0}
                </span>
                <span className="text-sm text-emerald-600">
                  {isLoading ? '' : `+${item?.todayNew ?? 0} today`}
                </span>
              </div>
              {card.key === 'tasks' && (
                <div className="mt-2 text-xs text-slate-600 flex gap-4">
                  <span>Running: {isLoading ? '—' : item?.running ?? 0}</span>
                  <span>Failed: {isLoading ? '—' : item?.failed ?? 0}</span>
                </div>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
