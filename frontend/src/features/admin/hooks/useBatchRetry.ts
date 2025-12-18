import { useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { BatchRetryRequest, BatchRetryResponse } from '../types'

export function useBatchRetry() {
  const queryClient = useQueryClient()
  return useMutation<BatchRetryResponse, Error, BatchRetryRequest>({
    mutationFn: (payload: BatchRetryRequest) => adminApi.batchRetry(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'tasks'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'task-statistics'] })
    },
  })
}
