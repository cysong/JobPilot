import { useEffect, useMemo, useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { RefreshCw, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import type { TaskListItem } from '../types'
import { ApiError } from '@/types/api'

interface TaskCardProps {
  item: TaskListItem
  onRetry: (taskId: string) => Promise<void>
}

function formatElapsedDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

function parseApiDateMs(value?: string): number | null {
  if (!value) return null
  const hasTimezone = /([zZ]|[+-]\d{2}:\d{2})$/.test(value)
  const normalized = hasTimezone ? value : `${value}Z`
  const ms = Date.parse(normalized)
  return Number.isNaN(ms) ? null : ms
}

function normalizeRunningStartedMs(startedMs: number, createdMs: number | null): number {
  if (createdMs === null) return startedMs
  const diffMs = createdMs - startedMs
  const minOffsetMs = 10 * 60 * 60 * 1000
  const maxOffsetMs = 14 * 60 * 60 * 1000
  if (diffMs < minOffsetMs || diffMs > maxOffsetMs) return startedMs

  // Historical rows written with naive UTC may appear shifted by local TZ offset (e.g., +12/+13h).
  // Detect this signature and shift by rounded whole-hour offset.
  const roundedHourOffsetMs = Math.round(diffMs / (60 * 60 * 1000)) * 60 * 60 * 1000
  return startedMs + roundedHourOffsetMs
}

export function TaskCard({ item, onRetry }: TaskCardProps) {
  const [isRetrying, setIsRetrying] = useState(false)
  const [nowMs, setNowMs] = useState(() => Date.now())
  const { toast } = useToast()
  const isRunning = item.status === 'Running' && Boolean(item.startedAt)

  useEffect(() => {
    if (!isRunning) return
    const timer = window.setInterval(() => {
      setNowMs(Date.now())
    }, 1000)
    return () => window.clearInterval(timer)
  }, [isRunning])

  const runningDurationText = useMemo(() => {
    if (!isRunning || !item.startedAt) return null
    const startedMsRaw = parseApiDateMs(item.startedAt)
    if (startedMsRaw === null) return null
    const createdMs = parseApiDateMs(item.createdAt)
    const startedMs = normalizeRunningStartedMs(startedMsRaw, createdMs)
    return formatElapsedDuration(nowMs - startedMs)
  }, [isRunning, item.startedAt, item.createdAt, nowMs])

  const successDurationText = useMemo(() => {
    if (item.status !== 'Success') return null
    if (typeof item.executionTimeMs === 'number' && item.executionTimeMs >= 0) {
      return formatElapsedDuration(item.executionTimeMs)
    }
    if (!item.startedAt || !item.completedAt) return null
    const startedMs = parseApiDateMs(item.startedAt)
    const completedMs = parseApiDateMs(item.completedAt)
    if (startedMs === null || completedMs === null) return null
    return formatElapsedDuration(completedMs - startedMs)
  }, [item.status, item.executionTimeMs, item.startedAt, item.completedAt])

  const createdAtDate = useMemo(() => {
    const createdMs = parseApiDateMs(item.createdAt)
    if (createdMs === null) return new Date(item.createdAt)
    return new Date(createdMs)
  }, [item.createdAt])

  const handleRetry = async () => {
    setIsRetrying(true)
    try {
      await onRetry(item.id)
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error && error.message
            ? error.message
            : 'Failed to retry task. Please try again.'
      toast({
        title: 'Retry failed',
        description: message,
        variant: 'destructive',
      })
    } finally {
      setIsRetrying(false)
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-slate-200 p-3 md:flex-row md:items-center md:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{item.id}</Badge>
          <span className="font-semibold text-slate-900">{item.taskName}</span>
          <Badge variant={item.status === 'Failed' ? 'destructive' : 'outline'}>{item.status}</Badge>
        </div>
        <div className="text-xs text-slate-600">
          Worker: {item.workerId || 'n/a'} | Retry: {item.retryCount}/{item.maxRetries} | AI Cost: ${item.aiCost.toFixed(2)}
        </div>
        <div className="text-xs text-slate-500">
          Created {formatDistanceToNow(createdAtDate, { addSuffix: true })}
        </div>
        {runningDurationText && (
          <div className="text-xs text-emerald-700">
            Running for {runningDurationText}
          </div>
        )}
        {successDurationText && (
          <div className="text-xs text-emerald-700">
            Duration {successDurationText}
          </div>
        )}
        {item.errorMessage && <div className="text-xs text-red-600 line-clamp-1">{item.errorMessage}</div>}
      </div>
      {item.status !== 'Success' && (
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRetry} disabled={isRetrying}>
            {isRetrying ? (
              <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5 mr-2" />
            )}
            Retry
          </Button>
        </div>
      )}
    </div>
  )
}
