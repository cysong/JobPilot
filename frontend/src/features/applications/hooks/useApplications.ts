import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { applicationApi } from '@/api/applications'
import type {
    ApplicationListRequest,
    CreateApplicationRequest,
    RetryApplicationRequest,
    ApplicationResolution,
    ApplicationStatus,
} from '@/types/application'
import type { DocumentEditData, DocumentUpdatePayload } from '@/types/document'
import { useToast } from '@/components/ui/use-toast'
import { ApiError } from '@/types/api'

const extractErrorMessage = (error: unknown, fallback: string): string => {
    if (error instanceof ApiError) {
        return error.message
    }
    if (
        typeof error === 'object' &&
        error !== null &&
        'response' in error &&
        typeof (error as { response?: unknown }).response === 'object' &&
        (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail &&
        typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
    ) {
        return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || fallback
    }
    return fallback
}

export const useApplications = (filters: ApplicationListRequest, enabled = true) => {
    return useQuery({
        queryKey: ['applications', filters],
        queryFn: () => applicationApi.list(filters),
        placeholderData: keepPreviousData,
        enabled,
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
        onError: (error: unknown) => {
            const message = extractErrorMessage(error, 'Failed to create application')
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

    const updateStatus = useMutation({
        mutationFn: ({ id, status, note }: { id: string; status: ApplicationStatus; note?: string }) =>
            applicationApi.updateStatus(id, { status, note }),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            queryClient.invalidateQueries({ queryKey: ['applications', data.id] })
            queryClient.invalidateQueries({ queryKey: ['application', 'by-job', data.job_id] })
            toast({ title: 'Success', description: 'Application status updated' })
        },
        onError: (error: unknown) => {
            const message = extractErrorMessage(error, 'Failed to update status')
            toast({
                title: 'Error',
                description: message,
                variant: 'destructive'
            })
        }
    })

    const updateResolution = useMutation({
        mutationFn: ({ id, resolution, note }: { id: string; resolution: ApplicationResolution; note?: string }) =>
            applicationApi.updateResolution(id, { resolution, note }),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            queryClient.invalidateQueries({ queryKey: ['applications', data.id] })
            queryClient.invalidateQueries({ queryKey: ['application', 'by-job', data.job_id] })
            toast({ title: 'Success', description: 'Application resolution updated' })
        },
        onError: (error: unknown) => {
            const message = extractErrorMessage(error, 'Failed to update application resolution')
            toast({
                title: 'Error',
                description: message,
                variant: 'destructive'
            })
        }
    })

    return {
        createApplication,
        retryCoverLetter,
        updateStatus,
        updateResolution,
    }
}
