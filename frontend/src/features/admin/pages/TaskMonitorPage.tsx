import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { TaskFilters } from '../components/TaskFilters'
import { TaskList } from '../components/TaskList'
import { TaskStatistics } from '../components/TaskStatistics'
import { useTasks } from '../hooks/useTasks'
import { useTaskStatistics } from '../hooks/useTaskStatistics'
import { useRetryTask } from '../hooks/useRetryTask'

export default function TaskMonitorPage() {
  const [filters, setFilters] = useState<{
    status?: string
    taskType?: string
    workerId?: string
    keyword?: string
  }>({})

  const tasksQuery = useTasks({ ...filters, page: 1, pageSize: 20, status: filters.status })
  const statsQuery = useTaskStatistics({ status: filters.status, taskType: filters.taskType })
  const retryMutation = useRetryTask()

  const refresh = () => {
    tasksQuery.refetch()
    statsQuery.refetch()
  }

  const handleRetry = (taskId: string) => {
    retryMutation.mutate(taskId)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Task Monitor</h1>
          <p className="text-sm text-slate-600">Filter, inspect, and retry Celery tasks.</p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <TaskFilters onChange={setFilters} />

      <TaskList
        items={tasksQuery.data?.items || []}
        isLoading={tasksQuery.isLoading}
        onRetry={handleRetry}
      />

      <TaskStatistics items={statsQuery.data?.taskTypeStats || []} isLoading={statsQuery.isLoading} />
    </div>
  )
}
