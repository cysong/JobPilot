import client from './client'
import type {
  UserSkill,
  UserSkillCreate,
  UserSkillUpdate,
  UserSkillListResponse,
  SkillSyncResponse
} from '@/types/skill'

export const skillsApi = {
  /**
   * Get all skills for the current user
   */
  getSkills: async () => {
    const result = await client.get<UserSkillListResponse, UserSkillListResponse>('/skills')
    return result
  },

  /**
   * Manually add a new skill
   */
  createSkill: async (data: UserSkillCreate) => {
    const result = await client.post<UserSkill, UserSkill>('/skills', data)
    return result
  },

  /**
   * Update skill proficiency level
   */
  updateSkill: async (skillId: string, data: UserSkillUpdate) => {
    const result = await client.put<UserSkill, UserSkill>(`/skills/${skillId}`, data)
    return result
  },

  /**
   * Delete a skill
   */
  deleteSkill: async (skillId: string) => {
    await client.delete(`/skills/${skillId}`)
  },

  /**
   * Manually trigger skill aggregation
   */
  syncSkills: async () => {
    const result = await client.post<SkillSyncResponse, SkillSyncResponse>('/skills/sync')
    return result
  }
}
