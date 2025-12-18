import { useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { TaskRetryResponse } from '../types'

export function useRetryTask() {
  const queryClient = useQueryClient()
  return useMutation<TaskRetryResponse, Error, string>({
    mutationFn: (taskId: string) => adminApi.retryTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'tasks'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'task-statistics'] })
    },
  })
}
