import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useAICostDailyTrend(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'ai-cost-daily-trend', days],
    queryFn: () => adminApi.getAICostDailyTrend({ days }),
  })
}
