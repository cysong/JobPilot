import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'

export function useTasksExecutionTime(days: number = 30) {
  return useQuery({
    queryKey: ['admin', 'tasks-execution-time', days],
    queryFn: () => adminApi.getTasksExecutionTime({ days }),
  })
}
