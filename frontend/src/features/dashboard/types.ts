import type { ApplicationStatus } from '@/types/application'
import type { UserJobMatch } from '@/types/job'
import type { ResumeListItem } from '@/types/resume'
import type { UserSkill } from '@/types/skill'

export type DashboardMetricTone = 'default' | 'success' | 'warning'

export interface DashboardMetric {
  label: string
  value: number
  helper: string
  href: string
  tone?: DashboardMetricTone
}

export type PriorityActionTone = 'default' | 'success' | 'warning' | 'danger'

export interface DashboardPriorityAction {
  title: string
  description: string
  ctaLabel: string
  href: string
  tone: PriorityActionTone
  external?: boolean
}

export interface DashboardApplicationItem {
  id: string
  title: string
  company: string
  status: ApplicationStatus
  href: string
  actionLabel: string
  actionHref: string
  actionExternal?: boolean
  isExpired: boolean
  addedAt: string
}

export interface DashboardApplicationSnapshot {
  counts: Record<ApplicationStatus, number>
  activeCount: number
  attentionItems: DashboardApplicationItem[]
}

export interface DashboardResumeSummary {
  finalizedCount: number
  draftCount: number
  latestResume: ResumeListItem | null
  resumes: ResumeListItem[]
}

export interface DashboardSkillsSummary {
  total: number
  manualCount: number
  autoCount: number
  topSkills: UserSkill[]
}

export interface UserDashboardData {
  userName: string
  heroMessage: string
  metrics: DashboardMetric[]
  priorityAction: DashboardPriorityAction | null
  applications: DashboardApplicationSnapshot
  recommendedJobs: UserJobMatch[]
  savedJobs: UserJobMatch[]
  resumeSummary: DashboardResumeSummary
  skillsSummary: DashboardSkillsSummary
}
