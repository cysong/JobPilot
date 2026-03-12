import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { TaskFilters } from '../components/TaskFilters'
import { TaskList } from '../components/TaskList'
import { TaskStatistics } from '../components/TaskStatistics'
import { useTasks } from '../hooks/useTasks'
import { useTaskStatistics } from '../hooks/useTaskStatistics'
import { useRetryTask } from '../hooks/useRetryTask'
import { useTaskTypes } from '../hooks/useTaskTypes'

export default function TaskMonitorPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [filters, setFilters] = useState<{
    status?: string
    taskType?: string
    workerId?: string
    keyword?: string
  }>({
    status: searchParams.get('status') || undefined,
    taskType: searchParams.get('taskType') || undefined,
    workerId: searchParams.get('workerId') || undefined,
    keyword: searchParams.get('keyword') || undefined,
  })
  const [page, setPage] = useState(() => Number(searchParams.get('page')) || 1)
  const pageSize = 20

  const tasksQuery = useTasks({ ...filters, page, pageSize, status: filters.status })
  const statsQuery = useTaskStatistics({ status: filters.status, taskType: filters.taskType })
  const retryMutation = useRetryTask()
  const taskTypesQuery = useTaskTypes()
  const retryRefreshTimerRef = useRef<number | null>(null)
  const workerOptions = useMemo(() => {
    const values = new Set<string>()
    const items = tasksQuery.data?.items || []
    items.forEach((item) => {
      if (item.workerId) values.add(item.workerId)
    })
    if (filters.workerId) values.add(filters.workerId)
    return Array.from(values).sort((a, b) => a.localeCompare(b))
  }, [tasksQuery.data?.items, filters.workerId])

  useEffect(() => {
    const next = new URLSearchParams()
    if (filters.status) next.set('status', filters.status)
    if (filters.taskType) next.set('taskType', filters.taskType)
    if (filters.workerId) next.set('workerId', filters.workerId)
    if (filters.keyword) next.set('keyword', filters.keyword)
    if (page > 1) next.set('page', String(page))
    setSearchParams(next, { replace: true })
  }, [filters, page, setSearchParams])

  useEffect(() => {
    return () => {
      if (retryRefreshTimerRef.current !== null) {
        window.clearTimeout(retryRefreshTimerRef.current)
      }
    }
  }, [])

  const scheduleRetryRefresh = () => {
    if (retryRefreshTimerRef.current !== null) {
      window.clearTimeout(retryRefreshTimerRef.current)
    }

    retryRefreshTimerRef.current = window.setTimeout(() => {
      retryRefreshTimerRef.current = null
      tasksQuery.refetch()
      statsQuery.refetch()
    }, 1200)
  }

  const refresh = () => {
    if (retryRefreshTimerRef.current !== null) {
      window.clearTimeout(retryRefreshTimerRef.current)
      retryRefreshTimerRef.current = null
    }
    tasksQuery.refetch()
    statsQuery.refetch()
  }

  const handleRetry = async (taskId: string) => {
    await retryMutation.mutateAsync(taskId)
    scheduleRetryRefresh()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Task Monitor</h1>
          <p className="text-sm text-slate-600">Filter, inspect, and retry Celery tasks.</p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className={`h-4 w-4 mr-2 ${tasksQuery.isFetching || statsQuery.isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <TaskFilters
        status={filters.status}
        taskType={filters.taskType}
        workerId={filters.workerId}
        keyword={filters.keyword}
        taskTypesOptions={taskTypesQuery.data || []}
        workerOptions={workerOptions}
        onChange={(next) => {
          setFilters(next)
          setPage(1)
        }}
      />

      <TaskList
        items={tasksQuery.data?.items || []}
        isLoading={tasksQuery.isLoading}
        onRetry={handleRetry}
        page={page}
        pageSize={pageSize}
        total={tasksQuery.data?.total || 0}
        onPageChange={setPage}
      />

      <TaskStatistics items={statsQuery.data?.taskTypeStats || []} isLoading={statsQuery.isLoading} />
    </div>
  )
}
