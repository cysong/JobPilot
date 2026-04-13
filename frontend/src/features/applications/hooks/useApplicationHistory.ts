import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { applicationApi } from '@/api/applications'
import type { StatusHistoryEntry } from '@/types/application'

export const historyQueryKey = (applicationId: string) =>
    ['applications', applicationId, 'history'] as const

export const useApplicationStatusHistory = (applicationId: string) => {
    return useQuery({
        queryKey: historyQueryKey(applicationId),
        queryFn: () => applicationApi.getStatusHistory(applicationId),
        enabled: !!applicationId,
    })
}

export const useUpdateHistoryNote = (applicationId: string) => {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ historyId, note }: { historyId: string; note: string }): Promise<StatusHistoryEntry> =>
            applicationApi.updateHistoryNote(applicationId, historyId, note),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: historyQueryKey(applicationId) })
        },
    })
}
