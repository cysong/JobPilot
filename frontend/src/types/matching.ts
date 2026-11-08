import type { MatchLabelInfo } from '@/types/job'

export type { MatchLabelInfo }

export type MatchLabelValue = 'A' | 'B' | 'C' | 'D' | 'REJECT'

export const MATCH_REASON_TAGS = [
  'FAMILY',
  'TECH',
  'EXPERIENCE',
  'SENIORITY',
  'CONSTRAINT',
  'LOCATION',
  'OTHER',
] as const

export type MatchReasonTag = (typeof MATCH_REASON_TAGS)[number]

export interface RoleFamilyInfo {
  key: string
  label: string
  label_zh: string
  description: string
}

export interface ResumeRoleFamilyResponse {
  resume_id: string
  role_family: string | null
  role_family_source: string | null
}

export interface MatchLabelCreate {
  job_id: number
  label: MatchLabelValue
  reason_tags: MatchReasonTag[]
  note?: string | null
}

export interface TitleFamilyItem {
  title_key: string
  example_title: string
  status: 'classified' | 'ambiguous'
  role_family: string | null
  source: 'llm' | 'admin'
  families_version: string
  job_count: number
  updated_at: string
}

export interface TitleFamilyListParams {
  q?: string
  role_family?: string
  status?: 'classified' | 'ambiguous'
  limit?: number
  offset?: number
}

export interface TitleFamilyListResponse {
  items: TitleFamilyItem[]
  total: number
}

export interface TitleFamilyUpdateResponse {
  item: TitleFamilyItem
  jobs_changed: number
  jobs_to_pending: number
}
