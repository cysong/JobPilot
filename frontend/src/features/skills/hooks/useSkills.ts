import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { skillsApi } from '@/api/skills'
import type { UserSkillCreate, UserSkillUpdate } from '@/types/skill'
import { useToast } from '@/components/ui/use-toast'

/**
 * Hook to fetch all user skills
 */
export const useSkills = () => {
  return useQuery({
    queryKey: ['skills'],
    queryFn: () => skillsApi.getSkills(),
  })
}

/**
 * Hook for skill mutations (create, update, delete, sync)
 */
export const useSkillMutations = () => {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const createSkill = useMutation({
    mutationFn: (data: UserSkillCreate) => skillsApi.createSkill(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
      toast({
        title: 'Success',
        description: 'Skill added successfully'
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to add skill',
        variant: 'destructive'
      })
    }
  })

  const updateSkill = useMutation({
    mutationFn: ({ skillId, data }: { skillId: string; data: UserSkillUpdate }) =>
      skillsApi.updateSkill(skillId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
      toast({
        title: 'Success',
        description: 'Skill updated successfully'
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to update skill',
        variant: 'destructive'
      })
    }
  })

  const deleteSkill = useMutation({
    mutationFn: (skillId: string) => skillsApi.deleteSkill(skillId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
      toast({
        title: 'Success',
        description: 'Skill deleted successfully'
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to delete skill',
        variant: 'destructive'
      })
    }
  })

  const syncSkills = useMutation({
    mutationFn: () => skillsApi.syncSkills(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
      toast({
        title: 'Success',
        description: `Skills synchronized: ${data.total_skills} total (${data.manual_skills} manual, ${data.auto_skills} auto)`
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to sync skills',
        variant: 'destructive'
      })
    }
  })

  return {
    createSkill,
    updateSkill,
    deleteSkill,
    syncSkills
  }
}
