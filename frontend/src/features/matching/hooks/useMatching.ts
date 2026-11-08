import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { matchingApi } from '@/api/matching'
import { useToast } from '@/components/ui/use-toast'
import type { MatchLabelCreate, TitleFamilyListParams } from '@/types/matching'

export const useRoleFamilies = (enabled = true) =>
  useQuery({
    queryKey: ['role-families'],
    queryFn: matchingApi.getRoleFamilies,
    enabled,
    staleTime: 1000 * 60 * 60,
  })

export const useSetResumeRoleFamily = () => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: ({ resumeId, roleFamily }: { resumeId: string; roleFamily: string | null }) =>
      matchingApi.setResumeRoleFamily(resumeId, roleFamily),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      toast({
        title: 'Role family updated',
        description: 'New jobs are matched against this resume from the next matching run.',
      })
    },
    onError: () => {
      toast({ title: 'Error', description: 'Failed to update the role family', variant: 'destructive' })
    },
  })
}

export const useCreateMatchLabel = () => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: (data: MatchLabelCreate) => matchingApi.createLabel(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['job-matches'] })
      queryClient.invalidateQueries({ queryKey: ['job-match-detail', variables.job_id] })
      toast({ title: 'Label saved', description: `Labeled ${variables.label}` })
    },
    onError: () => {
      toast({ title: 'Error', description: 'Failed to save the label', variant: 'destructive' })
    },
  })
}

export const useTitleFamilies = (params: TitleFamilyListParams) =>
  useQuery({
    queryKey: ['admin', 'title-families', params],
    queryFn: () => matchingApi.getTitleFamilies(params),
  })

export const useUpdateTitleFamily = () => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: ({ title, roleFamily }: { title: string; roleFamily: string | null }) =>
      matchingApi.updateTitleFamily(title, roleFamily),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'title-families'] })
      toast({
        title: 'Title family updated',
        description: `${data.item.example_title}: ${data.jobs_changed} jobs changed, ${data.jobs_to_pending} sent to a description read.`,
      })
    },
    onError: () => {
      toast({ title: 'Error', description: 'Failed to update the title family', variant: 'destructive' })
    },
  })
}
