import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useTasksDailyTrend(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'tasks-daily-trend', days],
    queryFn: () => adminApi.getTasksDailyTrend({ days }),
  })
}
