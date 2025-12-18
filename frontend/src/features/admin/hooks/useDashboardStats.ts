import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import type { DashboardStats } from '../types'

export function useDashboardStats() {
  return useQuery<DashboardStats, Error>({
    queryKey: ['admin', 'dashboard-stats'],
    queryFn: () => adminApi.getDashboardStats(),
    staleTime: 30_000,
  })
}
