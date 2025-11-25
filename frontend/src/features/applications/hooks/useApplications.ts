import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { applicationApi } from '@/api/applications'
import type { CreateApplicationRequest } from '@/types/application'
import { useToast } from '@/components/ui/use-toast'
import { useNavigate } from 'react-router-dom'

export const useApplications = (page = 1, size = 20) => {
    return useQuery({
        queryKey: ['applications', page, size],
        queryFn: () => applicationApi.list(page, size),
    })
}

export const useApplication = (id: string) => {
    return useQuery({
        queryKey: ['applications', id],
        queryFn: () => applicationApi.get(id),
        enabled: !!id,
    })
}

export const useApplicationMutations = () => {
    const queryClient = useQueryClient()
    const { toast } = useToast()
    const navigate = useNavigate()

    const createApplication = useMutation({
        mutationFn: (data: CreateApplicationRequest) => applicationApi.create(data),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            toast({ title: 'Success', description: 'Application started successfully' })
            // We might want to navigate to the application list or detail, or just close the dialog
            // For now, let's let the component handle navigation if needed, or just invalidate
        },
        onError: (error: any) => {
            toast({
                title: 'Error',
                description: error.response?.data?.detail || 'Failed to create application',
                variant: 'destructive'
            })
        }
    })

    const retryCoverLetter = useMutation({
        mutationFn: (id: string) => applicationApi.retryCoverLetter(id),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['applications'] })
            queryClient.invalidateQueries({ queryKey: ['applications', data.id] })
            toast({ title: 'Success', description: 'Cover letter generation retried' })
        },
        onError: () => {
            toast({ title: 'Error', description: 'Failed to retry cover letter', variant: 'destructive' })
        }
    })

    return {
        createApplication,
        retryCoverLetter
    }
}
