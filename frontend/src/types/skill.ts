/**
 * User skill management types
 */

export enum ProficiencyLevel {
  BEGINNER = 'beginner',
  INTERMEDIATE = 'intermediate',
  ADVANCED = 'advanced',
  EXPERT = 'expert'
}

export interface UserSkill {
  id: string
  user_id: number
  skill_name: string
  proficiency_level: ProficiencyLevel
  is_manual: boolean
  manual_proficiency: ProficiencyLevel | null
  source_count: number
  last_seen_at: string | null
  created_at: string
  updated_at: string
}

export interface UserSkillCreate {
  skill_name: string
  proficiency_level: ProficiencyLevel
}

export interface UserSkillUpdate {
  proficiency_level: ProficiencyLevel
}

export interface UserSkillListResponse {
  items: UserSkill[]
  total: number
  manual_count: number
  auto_count: number
}

export interface SkillSyncResponse {
  message: string
  total_skills: number
  manual_skills: number
  auto_skills: number
}
