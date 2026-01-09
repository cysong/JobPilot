import { useState } from 'react'
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

export function TaskCard({ item, onRetry }: TaskCardProps) {
  const [isRetrying, setIsRetrying] = useState(false)
  const { toast } = useToast()

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
          Created {formatDistanceToNow(new Date(item.createdAt), { addSuffix: true })}
        </div>
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
