import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { TaskDetailResponse } from '../types'

export function useTaskDetail(taskId: string, enabled: boolean) {
  return useQuery<TaskDetailResponse, Error>({
    queryKey: ['admin', 'task-detail', taskId],
    queryFn: () => adminApi.getTaskDetail(taskId),
    enabled,
  })
}
