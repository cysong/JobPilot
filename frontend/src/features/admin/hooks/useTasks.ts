import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { TaskListResponse } from '../types'

export interface TaskQueryParams {
  status?: string
  taskType?: string
  workerId?: string
  keyword?: string
  startTime?: string
  endTime?: string
  page?: number
  pageSize?: number
}

export function useTasks(params: TaskQueryParams) {
  return useQuery<TaskListResponse, Error>({
    queryKey: ['admin', 'tasks', params],
    queryFn: () => adminApi.getTasks(params),
    placeholderData: keepPreviousData,
    // Refresh every 30s while the admin tab is in the foreground; pause
    // when the tab is hidden; force-refresh as soon as the user comes back.
    // (Overrides the global refetchOnWindowFocus:false in App.tsx.)
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })
}
