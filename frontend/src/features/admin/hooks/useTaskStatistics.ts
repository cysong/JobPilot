import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { TaskStatisticsResponse } from '../types'

export function useTaskStatistics(params: {
  status?: string
  taskType?: string
  startTime?: string
  endTime?: string
}) {
  return useQuery<TaskStatisticsResponse, Error>({
    queryKey: ['admin', 'task-statistics', params],
    queryFn: () => adminApi.getTaskStatistics(params),
    keepPreviousData: true,
  })
}
