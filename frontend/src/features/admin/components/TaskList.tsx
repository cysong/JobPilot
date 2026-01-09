import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Pagination } from '@/components/ui/pagination'
import type { TaskListItem } from '../types'

interface Props {
  items: TaskListItem[]
  isLoading: boolean
  onRetry: (taskId: string) => void
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function TaskList({ items, isLoading, onRetry, page, pageSize, total, onPageChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <Card className="shadow-sm border-slate-200">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-slate-900">Tasks</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <div className="text-sm text-slate-600">Loading tasks...</div>}
        {!isLoading && items.length === 0 && <div className="text-sm text-slate-600">No tasks found.</div>}
        {!isLoading &&
          items.map((t) => (
            <div
              key={t.id}
              className="flex flex-col gap-2 rounded-lg border border-slate-200 p-3 md:flex-row md:items-center md:justify-between"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{t.id}</Badge>
                  <span className="font-semibold text-slate-900">{t.taskName}</span>
                  <Badge variant={t.status === 'Failed' ? 'destructive' : 'outline'}>{t.status}</Badge>
                </div>
                <div className="text-xs text-slate-600">
                  Worker: {t.workerId || 'n/a'} | Retry: {t.retryCount}/{t.maxRetries} | AI Cost: ${t.aiCost.toFixed(2)}
                </div>
                <div className="text-xs text-slate-500">
                  Created {formatDistanceToNow(new Date(t.createdAt), { addSuffix: true })}
                </div>
                {t.errorMessage && <div className="text-xs text-red-600 line-clamp-1">{t.errorMessage}</div>}
              </div>
              {t.status !== 'Success' && (
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => onRetry(t.id)}>
                    Retry
                  </Button>
                </div>
              )}
            </div>
          ))}
        <div className="space-y-2 pt-2">
          <div className="text-sm text-slate-600">
            Page {page} / {totalPages} | Total {total}
          </div>
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
        </div>
      </CardContent>
    </Card>
  )
}
