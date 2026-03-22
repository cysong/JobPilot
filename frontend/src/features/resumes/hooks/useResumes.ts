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

export const useTargetJobTitleOptions = (keyword: string, enabled = true) => {
    return useQuery({
        queryKey: ['resume-target-job-title-options', keyword],
        queryFn: () => resumeApi.getTargetJobTitleOptions(keyword || undefined),
        enabled,
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

export const useUpdateTargetJobTitles = () => {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ id, targetJobTitles }: { id: string; targetJobTitles: string[] }) =>
      resumeApi.updateTargetJobTitles(id, { target_job_titles: targetJobTitles }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      queryClient.invalidateQueries({ queryKey: ['resumes', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['resume-edit', variables.id] })
      toast({ title: 'Success', description: 'Target roles updated successfully' })
    },
    onError: (error) => {
      const description = error instanceof ApiError
        ? error.message
        : 'Failed to update target roles'
      toast({
        title: 'Error',
        description,
        variant: 'destructive',
      })
    },
  })
}

// Hook for creating resume without auto-navigation (for config-driven DocumentEditPage)
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
            queryClient.invalidateQueries({ queryKey: ['resumes', data.id] })
            queryClient.invalidateQueries({ queryKey: ['resume-edit', data.id] })
            toast({ title: 'Success', description: 'Resume finalized successfully' })
        },
        onError: () => {
            toast({ title: 'Error', description: 'Failed to finalize resume', variant: 'destructive' })
        }
    })

    return {
        deleteResume,
        finalizeResume
    }
}
