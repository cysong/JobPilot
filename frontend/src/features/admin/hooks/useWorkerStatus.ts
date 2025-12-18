import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { WorkerMonitorResponse } from '../types'

export function useWorkerStatus() {
  return useQuery<WorkerMonitorResponse, Error>({
    queryKey: ['admin', 'workers'],
    queryFn: () => adminApi.getWorkerStatus(),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
}
