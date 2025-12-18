import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { TaskTypeStats } from '../types'

interface Props {
  items: TaskTypeStats[]
  isLoading: boolean
}

export function TaskStatistics({ items, isLoading }: Props) {
  return (
    <Card className="shadow-sm border-slate-200">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-slate-900">Task Statistics</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <div className="text-sm text-slate-600">Loading statistics...</div>}
        {!isLoading && items.length === 0 && <div className="text-sm text-slate-600">No statistics.</div>}
        {!isLoading &&
          items.map((item) => (
            <div
              key={item.taskType}
              className="flex flex-col gap-1 rounded-lg border border-slate-200 p-3"
            >
              <div className="flex items-center justify-between">
                <div className="font-semibold text-slate-900">{item.taskType}</div>
                <div className="text-xs text-slate-600">Trend: {item.trend}</div>
              </div>
              <div className="text-xs text-slate-600">
                Avg Duration: {item.avgDurationMs ? `${Math.round(item.avgDurationMs)} ms` : '—'} · Failure Rate:{' '}
                {item.failureRatePct?.toFixed(1) ?? '0'}% · Today: {item.todayFailureRatePct?.toFixed(1) ?? '0'}% · Daily
                Cost: ${item.dailyCost.toFixed(2)}
              </div>
              <div className="text-xs text-slate-600">Total: {item.totalCount}</div>
            </div>
          ))}
      </CardContent>
    </Card>
  )
}
