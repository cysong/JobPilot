import { useQuery } from '@tanstack/react-query'
import { authApi } from '@/api/auth'

/**
 * Whether sign-up is open. undefined while loading; true if the status call fails
 * (the backend still refuses registration when it is closed).
 */
export const useRegistrationAllowed = (): boolean | undefined => {
  const { data, isError } = useQuery({
    queryKey: ['auth', 'registration-status'],
    queryFn: authApi.getRegistrationStatus,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })
  if (isError) return true
  return data?.allowed
}
