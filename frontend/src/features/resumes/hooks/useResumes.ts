import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { resumeApi } from '@/api/resumes'
import type { CreateResumeRequest, UpdateResumeRequest } from '@/types/resume'
import type { DocumentEditData, DocumentUpdatePayload } from '@/types/document'
import { useToast } from '@/components/ui/use-toast'
import { useNavigate } from 'react-router-dom'

export const useResumes = () => {
    return useQuery({
        queryKey: ['resumes'],
        queryFn: () => resumeApi.getResumes(),
    })
}

export const useResume = (id: string) => {
    return useQuery({
        queryKey: ['resumes', id],
        queryFn: () => resumeApi.getResumeById(id),
        enabled: !!id,
    })
}

export const useResumeEdit = (resumeId: string) => {
    return useQuery<DocumentEditData>({
        queryKey: ['resume-edit', resumeId],
        queryFn: () => resumeApi.getResumeForEdit(resumeId),
        enabled: !!resumeId,
    })
}

export const useUpdateResumeContent = () => {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, ...data }: { id: string } & DocumentUpdatePayload) =>
            resumeApi.updateResumeContent(id, data),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ['resumes'] })
            queryClient.invalidateQueries({ queryKey: ['resume-edit', variables.id] })
        },
    })
}

export const useResumeMutations = () => {
    const queryClient = useQueryClient()
    const { toast } = useToast()
    const navigate = useNavigate()

    const createResume = useMutation({
        mutationFn: (data: CreateResumeRequest) => resumeApi.createResume(data),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['resumes'] })
            toast({ title: 'Success', description: 'Resume created successfully' })
            navigate(`/resumes/${data.id}`)
        },
        onError: () => {
            toast({ title: 'Error', description: 'Failed to create resume', variant: 'destructive' })
        }
    })

    const updateResume = useMutation({
        mutationFn: ({ id, data }: { id: string; data: UpdateResumeRequest }) =>
            resumeApi.updateResume(id, data),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['resumes'] })
            queryClient.invalidateQueries({ queryKey: ['resumes', data.id] })
            toast({ title: 'Success', description: 'Resume updated successfully' })
        },
        onError: () => {
            toast({ title: 'Error', description: 'Failed to update resume', variant: 'destructive' })
        }
    })

    const deleteResume = useMutation({
        mutationFn: (id: string) => resumeApi.deleteResume(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['resumes'] })
            toast({ title: 'Success', description: 'Resume deleted successfully' })
        },
        onError: () => {
            toast({ title: 'Error', description: 'Failed to delete resume', variant: 'destructive' })
        }
    })

    const finalizeResume = useMutation({
        mutationFn: (id: string) => resumeApi.finalizeResume(id),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['resumes'] })
            queryClient.invalidateQueries({ queryKey: ['resumes', data.id] })
            toast({ title: 'Success', description: 'Resume finalized successfully' })
        },
        onError: () => {
            toast({ title: 'Error', description: 'Failed to finalize resume', variant: 'destructive' })
        }
    })

    return {
        createResume,
        updateResume,
        deleteResume,
        finalizeResume
    }
}
