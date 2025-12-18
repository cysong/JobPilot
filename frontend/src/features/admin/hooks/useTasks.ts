import { useQuery } from '@tanstack/react-query'
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
    keepPreviousData: true,
  })
}
