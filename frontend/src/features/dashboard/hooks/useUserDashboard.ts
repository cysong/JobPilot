import { useQueries } from '@tanstack/react-query'

import { applicationApi } from '@/api/applications'
import { jobsApi } from '@/api/jobs'
import { resumeApi } from '@/api/resumes'
import { skillsApi } from '@/api/skills'
import { useAuthStore } from '@/store/authStore'
import type { Application, ApplicationStatus } from '@/types/application'
import type { UserJobMatch } from '@/types/job'
import type { ResumeListItem } from '@/types/resume'
import type { UserSkill } from '@/types/skill'
import type {
  DashboardApplicationItem,
  DashboardApplicationSnapshot,
  DashboardMetric,
  DashboardPriorityAction,
  DashboardResumeSummary,
  DashboardSkillsSummary,
  UserDashboardData,
} from '@/features/dashboard/types'

const DASHBOARD_APPLICATION_PAGE_SIZE = 100
const DASHBOARD_MATCH_LIMIT = 6
const DASHBOARD_SAVED_LIMIT = 4
const DASHBOARD_TOP_SKILLS_LIMIT = 8

const INITIAL_STATUS_COUNTS: Record<ApplicationStatus, number> = {
  Pending: 0,
  Tailoring: 0,
  Ready: 0,
  Applied: 0,
  PhoneScreen: 0,
  Interviewing: 0,
  Offer: 0,
  Rejected: 0,
  Failed: 0,
}

const getCompanyName = (application: Application): string =>
  application.job?.company_name || application.job?.advertiser_name || 'Unknown Company'

const buildApplicationItem = (application: Application): DashboardApplicationItem => {
  const detailHref = `/applications/${application.id}`
  const isExpired = Boolean(application.job?.is_expired)
  const shareLink = application.job?.share_link || ''

  let actionLabel = 'Open'
  let actionHref = detailHref
  let actionExternal = false

  if (application.status === 'Ready' && shareLink) {
    actionLabel = 'Apply'
    actionHref = shareLink
    actionExternal = true
  } else if (application.status === 'Failed') {
    actionLabel = 'Review'
  } else if (application.status === 'Pending' || application.status === 'Tailoring') {
    actionLabel = 'Check Progress'
  }

  return {
    id: application.id,
    title: application.job?.title || 'Unknown Job',
    company: getCompanyName(application),
    status: application.status,
    href: detailHref,
    actionLabel,
    actionHref,
    actionExternal,
    isExpired,
    updatedAt: application.updated_at,
  }
}

const getAttentionApplications = (applications: Application[]): DashboardApplicationItem[] => {
  const scoreApplication = (application: Application): number => {
    switch (application.status) {
      case 'Ready':
        return 500
      case 'Failed':
        return 400
      case 'Tailoring':
        return 300
      case 'Pending':
        return 200
      case 'Applied':
        return 100
      default:
        return 0
    }
  }

  return [...applications]
    .sort((a, b) => {
      const scoreDelta = scoreApplication(b) - scoreApplication(a)
      if (scoreDelta !== 0) return scoreDelta
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    })
    .slice(0, 5)
    .map(buildApplicationItem)
}

const buildApplicationSnapshot = (applications: Application[]): DashboardApplicationSnapshot => {
  const counts = applications.reduce<Record<ApplicationStatus, number>>((acc, application) => {
    acc[application.status] += 1
    return acc
  }, { ...INITIAL_STATUS_COUNTS })

  return {
    counts,
    activeCount:
      counts.Pending +
      counts.Tailoring +
      counts.Ready +
      counts.Applied +
      counts.PhoneScreen +
      counts.Interviewing,
    attentionItems: getAttentionApplications(applications),
  }
}

const buildResumeSummary = (resumes: ResumeListItem[]): DashboardResumeSummary => {
  const sorted = [...resumes].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
  return {
    finalizedCount: resumes.filter((resume) => !resume.is_draft).length,
    draftCount: resumes.filter((resume) => resume.is_draft).length,
    latestResume: sorted[0] || null,
    resumes: sorted,
  }
}

const buildSkillsSummary = (skills: UserSkill[], manualCount: number, autoCount: number): DashboardSkillsSummary => {
  const topSkills = [...skills]
    .sort((a, b) => {
      if (b.source_count !== a.source_count) return b.source_count - a.source_count
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    })
    .slice(0, DASHBOARD_TOP_SKILLS_LIMIT)

  return {
    total: skills.length,
    manualCount,
    autoCount,
    topSkills,
  }
}

const buildMetrics = ({
  applicationSnapshot,
  readyToApply,
  savedCount,
  finalizedResumeCount,
}: {
  applicationSnapshot: DashboardApplicationSnapshot
  readyToApply: number
  savedCount: number
  finalizedResumeCount: number
}): DashboardMetric[] => [
  {
    label: 'Active Applications',
    value: applicationSnapshot.activeCount,
    helper: 'Applications in progress',
    href: '/applications',
  },
  {
    label: 'Ready to Apply',
    value: readyToApply,
    helper: 'Applications with materials ready',
    href: '/applications?status=Ready',
    tone: readyToApply > 0 ? 'success' : 'default',
  },
  {
    label: 'Saved Jobs',
    value: savedCount,
    helper: 'Jobs kept for follow-up',
    href: '/jobs?view=saved',
  },
  {
    label: 'Final Resumes',
    value: finalizedResumeCount,
    helper: 'Templates ready for applications',
    href: '/resumes',
    tone: finalizedResumeCount === 0 ? 'warning' : 'default',
  },
]

const buildPriorityAction = ({
  applications,
  matches,
  resumeSummary,
}: {
  applications: Application[]
  matches: UserJobMatch[]
  resumeSummary: DashboardResumeSummary
}): DashboardPriorityAction | null => {
  const readyApplication = applications.find(
    (application) => application.status === 'Ready' && application.job?.share_link
  )
  if (readyApplication?.job?.share_link) {
    return {
      title: 'Apply while materials are ready',
      description: `${readyApplication.job.title || 'This application'} is ready to submit with tailored materials.`,
      ctaLabel: 'Apply Now',
      href: readyApplication.job.share_link,
      tone: 'success',
      external: true,
    }
  }

  const failedApplication = applications.find((application) => application.status === 'Failed')
  if (failedApplication) {
    return {
      title: 'Review a failed generation',
      description: `${failedApplication.job?.title || 'An application'} needs attention before it can move forward.`,
      ctaLabel: 'Open Application',
      href: `/applications/${failedApplication.id}`,
      tone: 'danger',
    }
  }

  const inProgressApplication = applications.find(
    (application) => application.status === 'Pending' || application.status === 'Tailoring'
  )
  if (inProgressApplication) {
    return {
      title: 'Check your in-progress application',
      description: `${inProgressApplication.job?.title || 'This application'} is still generating tailored materials.`,
      ctaLabel: 'Check Progress',
      href: `/applications/${inProgressApplication.id}`,
      tone: 'warning',
    }
  }

  const topMatch = matches.find((match) => !match.job.has_application)
  if (topMatch) {
    return {
      title: 'Review your strongest job match',
      description: `${topMatch.job.title} has a ${Math.round(topMatch.skill_match_score)}% skill match.`,
      ctaLabel: 'View Job',
      href: `/jobs/${topMatch.job.id}`,
      tone: 'default',
    }
  }

  if (resumeSummary.finalizedCount === 0 && resumeSummary.latestResume) {
    return {
      title: 'Finalize a resume before applying',
      description: 'You need at least one finalized resume to support recommended applications.',
      ctaLabel: 'Manage Resumes',
      href: '/resumes',
      tone: 'warning',
    }
  }

  if (resumeSummary.draftCount > 0) {
    return {
      title: 'Review your latest draft resume',
      description: 'A polished finalized resume improves matching and application quality.',
      ctaLabel: 'Open Resumes',
      href: '/resumes',
      tone: 'default',
    }
  }

  return {
    title: 'Browse new opportunities',
    description: 'Your dashboard is clear. Explore recent jobs and build your next shortlist.',
    ctaLabel: 'Browse Jobs',
    href: '/jobs',
    tone: 'default',
  }
}

const buildHeroMessage = ({
  applications,
  matches,
  resumeSummary,
}: {
  applications: DashboardApplicationSnapshot
  matches: UserJobMatch[]
  resumeSummary: DashboardResumeSummary
}): string => {
  if (applications.counts.Ready > 0) {
    return `You have ${applications.counts.Ready} application${applications.counts.Ready > 1 ? 's' : ''} ready to submit.`
  }
  if (applications.counts.Failed > 0) {
    return `You have ${applications.counts.Failed} failed generation${applications.counts.Failed > 1 ? 's' : ''} to review.`
  }
  if (applications.counts.Pending + applications.counts.Tailoring > 0) {
    const total = applications.counts.Pending + applications.counts.Tailoring
    return `${total} application${total > 1 ? 's are' : ' is'} currently being prepared.`
  }
  if (matches.length > 0) {
    return `${matches.length} strong job matches are ready for review.`
  }
  if (resumeSummary.finalizedCount === 0) {
    return 'Finalize a resume to unlock better matching and faster applications.'
  }
  return 'Your dashboard is clear. Use today to review fresh opportunities.'
}

export const useUserDashboard = () => {
  const user = useAuthStore((state) => state.user)

  const results = useQueries({
    queries: [
      {
        queryKey: ['dashboard', 'applications'],
        queryFn: () =>
          applicationApi.list({
            page: 1,
            page_size: DASHBOARD_APPLICATION_PAGE_SIZE,
          }),
      },
      {
        queryKey: ['dashboard', 'job-matches'],
        queryFn: () =>
          jobsApi.getJobMatches({
            min_score: 50,
            limit: DASHBOARD_MATCH_LIMIT,
            offset: 0,
          }),
      },
      {
        queryKey: ['dashboard', 'saved-jobs'],
        queryFn: () =>
          jobsApi.getSavedJobs({
            page: 1,
            page_size: DASHBOARD_SAVED_LIMIT,
          }),
      },
      {
        queryKey: ['dashboard', 'resumes'],
        queryFn: () => resumeApi.getResumes(),
      },
      {
        queryKey: ['dashboard', 'skills'],
        queryFn: () => skillsApi.getSkills(),
      },
    ],
  })

  const [applicationsQuery, matchesQuery, savedJobsQuery, resumesQuery, skillsQuery] = results
  const applications = applicationsQuery.data?.items || []
  const matches = matchesQuery.data || []
  const savedJobs =
    savedJobsQuery.data?.items.map<UserJobMatch>((item) => ({
      id: `saved-${item.job.id}`,
      job: {
        ...item.job,
        source: item.job.source || null,
      },
      skill_match_score: 0,
      resume_match_score: null,
      ai_match_score: null,
      recommended_resume: null,
      skill_match_details: {},
      ai_analysis: null,
      calculated_at: item.saved_at,
      ai_analyzed_at: null,
    })) || []
  const resumes = resumesQuery.data?.items || []
  const skills = skillsQuery.data?.items || []

  const applicationSnapshot = buildApplicationSnapshot(applications)
  const resumeSummary = buildResumeSummary(resumes)
  const skillsSummary = buildSkillsSummary(
    skills,
    skillsQuery.data?.manual_count || 0,
    skillsQuery.data?.auto_count || 0
  )

  const dashboardData: UserDashboardData = {
    userName: user?.full_name || 'there',
    heroMessage: buildHeroMessage({
      applications: applicationSnapshot,
      matches,
      resumeSummary,
    }),
    metrics: buildMetrics({
      applicationSnapshot,
      readyToApply: applicationSnapshot.counts.Ready,
      savedCount: savedJobsQuery.data?.total || 0,
      finalizedResumeCount: resumeSummary.finalizedCount,
    }),
    priorityAction: buildPriorityAction({
      applications,
      matches,
      resumeSummary,
    }),
    applications: applicationSnapshot,
    recommendedJobs: matches,
    savedJobs,
    resumeSummary,
    skillsSummary,
  }

  return {
    data: dashboardData,
    isLoading: results.some((query) => query.isLoading),
    isFetching: results.some((query) => query.isFetching),
    isApplicationsError: applicationsQuery.isError,
    isMatchesError: matchesQuery.isError,
    isSavedJobsError: savedJobsQuery.isError,
    isResumesError: resumesQuery.isError,
    isSkillsError: skillsQuery.isError,
  }
}
