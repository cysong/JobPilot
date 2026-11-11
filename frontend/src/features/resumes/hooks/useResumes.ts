import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { resumeApi } from '@/api/resumes'
import type { CreateResumeRequest } from '@/types/resume'
import type { DocumentEditData, DocumentUpdatePayload } from '@/types/document'
import { ApiError } from '@/types/api'
import { useToast } from '@/components/ui/use-toast'

export const useResumes = () => {
    return useQuery({
        queryKey: ['resumes'],
        queryFn: () => resumeApi.getResumes(),
    })
}

export const useFormalResumeLimit = () => {
    return useQuery({
        queryKey: ['resume-formal-limit'],
        queryFn: () => resumeApi.getFormalResumeLimit(),
    })
}

export const useResumeForEdit = (resumeId: string) => {
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

export const useUpdateResumeTitle = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      resumeApi.updateResumeTitle(id, { title }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      queryClient.invalidateQueries({ queryKey: ['resume-edit', variables.id] })
    },
  })
}

export const useCreateResume = () => {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: CreateResumeRequest) => resumeApi.createResume(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['resumes'] })
        },
    })
}

export const useResumeMutations = () => {
    const queryClient = useQueryClient()
    const { toast } = useToast()

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
            queryClient.invalidateQueries({ queryKey: ['resume-formal-limit'] })
            queryClient.invalidateQueries({ queryKey: ['resumes', data.id] })
            queryClient.invalidateQueries({ queryKey: ['resume-edit', data.id] })
            toast({ title: 'Success', description: 'Resume finalized successfully' })
        },
        onError: (error) => {
            const description = error instanceof ApiError
              ? error.message
              : 'Failed to finalize resume'
            toast({ title: 'Error', description, variant: 'destructive' })
        }
    })

    return {
        deleteResume,
        finalizeResume
    }
}
