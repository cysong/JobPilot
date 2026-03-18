import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useJobsTimeScatter(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'jobs-time-scatter', days],
    queryFn: () => adminApi.getJobsTimeScatter({ days }),
  })
}
