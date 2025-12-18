import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { WorkerMonitorResponse } from '../types'

interface Props {
  data: WorkerMonitorResponse | undefined
  isLoading: boolean
}

export function WorkerMonitor({ data, isLoading }: Props) {
  return (
    <Card className="shadow-sm border-slate-200">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold text-slate-900">Workers</CardTitle>
        <div className="flex gap-4 text-sm text-slate-600">
          <span>Active: {isLoading ? '—' : data?.activeCount ?? 0}</span>
          <span>Running: {isLoading ? '—' : data?.runningTasks ?? 0}</span>
          <span>Queued: {isLoading ? '—' : data?.queuedTasks ?? 0}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {(data?.workers || []).map((w) => (
          <div
            key={w.id}
            className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
          >
            <div>
              <div className="font-semibold text-slate-900">{w.id}</div>
              <div className="text-xs text-slate-600">{w.hostname}</div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-700">Running: {w.currentTasks}</span>
              <Badge variant={w.status === 'active' ? 'success' : 'secondary'}>
                {w.status === 'active' ? 'Active' : 'Offline'}
              </Badge>
            </div>
          </div>
        ))}
        {(!data || data.workers.length === 0) && (
          <div className="text-sm text-slate-600">No workers detected.</div>
        )}
      </CardContent>
    </Card>
  )
}
