import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useAITokensDailyTrend(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'ai-tokens-daily-trend', days],
    queryFn: () => adminApi.getAITokensDailyTrend({ days }),
  })
}
