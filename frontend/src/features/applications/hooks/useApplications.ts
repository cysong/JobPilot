import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { applicationApi } from '@/api/applications'
import type {
    ApplicationListRequest,
    CreateApplicationRequest,
    RetryApplicationRequest
} from '@/types/application'
import type { DocumentEditData, DocumentUpdatePayload } from '@/types/document'
import { useToast } from '@/components/ui/use-toast'
import { ApiError } from '@/types/api'

export const useApplications = (filters: ApplicationListRequest) => {
    return useQuery({
        queryKey: ['applications', filters],
        queryFn: () => applicationApi.list(filters),
    })
}

export const useApplication = (id: string) => {
    return useQuery({
        queryKey: ['applications', id],
        queryFn: () => applicationApi.get(id),
        enabled: !!id,
    })
}

export const useTailoredResumeForEdit = (applicationId: string) => {
    return useQuery<DocumentEditData>({
        queryKey: ['tailored-resume-edit', applicationId],
        queryFn: () => applicationApi.getTailoredResumeForEdit(applicationId),
        enabled: !!applicationId,
    })
}

export const useUpdateTailoredResumeContent = () => {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, ...data }: { id: string} & DocumentUpdatePayload) =>
            applicationApi.updateTailoredResume(id, data),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            queryClient.invalidateQueries({ queryKey: ['tailored-resume-edit', variables.id] })
        },
    })
}

export const useCoverLetterForEdit = (applicationId: string) => {
    return useQuery<DocumentEditData>({
        queryKey: ['cover-letter-edit', applicationId],
        queryFn: () => applicationApi.getCoverLetterForEdit(applicationId),
        enabled: !!applicationId,
    })
}

export const useUpdateCoverLetterContent = () => {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, ...data }: { id: string } & DocumentUpdatePayload) =>
            applicationApi.updateCoverLetter(id, data),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            queryClient.invalidateQueries({ queryKey: ['cover-letter-edit', variables.id] })
        },
    })
}

export const useApplicationMutations = () => {
    const queryClient = useQueryClient()
    const { toast } = useToast()

    const createApplication = useMutation({
        mutationFn: (data: CreateApplicationRequest) => applicationApi.create(data),
        onSuccess: (data) => {
            // Invalidate all application-related queries for immediate UI update
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            // Also invalidate the by-job query to update JobDetailPage
            queryClient.invalidateQueries({ queryKey: ['application', 'by-job', data.job_id] })
            toast({ title: 'Success', description: 'Application started successfully' })
        },
        onError: (error: any) => {
            const message = error instanceof ApiError
                ? error.message
                : error?.response?.data?.detail || 'Failed to create application'
            toast({
                title: 'Error',
                description: message,
                variant: 'destructive'
            })
        }
    })

    const retryCoverLetter = useMutation({
        mutationFn: ({ id, payload }: { id: string; payload?: RetryApplicationRequest }) =>
            applicationApi.retryCoverLetter(id, payload),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            queryClient.invalidateQueries({ queryKey: ['applications', data.id] })
            toast({ title: 'Success', description: 'Resume and cover letter regeneration started' })
        },
        onError: () => {
            toast({ title: 'Error', description: 'Failed to retry generation', variant: 'destructive' })
        }
    })

    return {
        createApplication,
        retryCoverLetter
    }
}
