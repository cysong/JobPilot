import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useTaskTypes() {
  return useQuery({
    queryKey: ['admin', 'task-types'],
    queryFn: () => adminApi.getTaskTypes(),
    staleTime: 5 * 60 * 1000,
  })
}
