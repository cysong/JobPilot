import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useJobsDailyTrend(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'jobs-daily-trend', days],
    queryFn: () => adminApi.getJobsDailyTrend({ days }),
  })
}
