import { useMutation } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { TaskRetryResponse } from '../types'

export function useRetryTask() {
  return useMutation<TaskRetryResponse, Error, string>({
    mutationFn: (taskId: string) => adminApi.retryTask(taskId),
  })
}
