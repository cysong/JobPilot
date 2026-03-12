import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Pagination } from '@/components/ui/pagination'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import type { TaskListItem } from '../types'
import { TaskCard } from './TaskCard'

interface Props {
  items: TaskListItem[]
  isLoading: boolean
  onRetry: (taskId: string) => Promise<void>
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function TaskList({
  items,
  isLoading,
  onRetry,
  page,
  pageSize,
  total,
  onPageChange,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const [listParentRef] = useAutoAnimate<HTMLDivElement>({
    duration: 280,
    easing: 'ease-out',
  })

  return (
    <Card className="shadow-sm border-slate-200">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-slate-900">Tasks({total})</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <div className="text-sm text-slate-600">Loading tasks...</div>}
        {!isLoading && items.length === 0 && <div className="text-sm text-slate-600">No tasks found.</div>}
        {!isLoading && (
          <div ref={listParentRef} className="space-y-3">
            {items.map((t) => (
              <TaskCard key={t.id} item={t} onRetry={onRetry} />
            ))}
          </div>
        )}
        <div className="space-y-2 pt-2">
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
        </div>
      </CardContent>
    </Card>
  )
}
