import { DashboardHero } from '@/features/dashboard/components/DashboardHero'
import { DashboardMetricCards } from '@/features/dashboard/components/DashboardMetricCards'
import { PriorityActionCard } from '@/features/dashboard/components/PriorityActionCard'
import { ApplicationPipelineCard } from '@/features/dashboard/components/ApplicationPipelineCard'
import { RecommendedJobsCard } from '@/features/dashboard/components/RecommendedJobsCard'
import { ResumeReadinessCard } from '@/features/dashboard/components/ResumeReadinessCard'
import { SkillsOverviewCard } from '@/features/dashboard/components/SkillsOverviewCard'
import { QuickLinksCard } from '@/features/dashboard/components/QuickLinksCard'
import { useUserDashboard } from '@/features/dashboard/hooks/useUserDashboard'

export default function UserDashboardPage() {
  const dashboard = useUserDashboard()
  const { data } = dashboard

  return (
    <div className="space-y-6">
      <DashboardHero
        userName={data.userName}
        message={data.heroMessage}
        isLoading={dashboard.isLoading}
      />

      <DashboardMetricCards metrics={data.metrics} isLoading={dashboard.isLoading} />

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="space-y-6 xl:col-span-8">
          <PriorityActionCard action={data.priorityAction} isLoading={dashboard.isLoading} />
          <ApplicationPipelineCard
            data={data.applications}
            isLoading={dashboard.isLoading}
            hasError={dashboard.isApplicationsError}
          />
          <RecommendedJobsCard
            recommendedJobs={data.recommendedJobs}
            savedJobs={data.savedJobs}
            isLoading={dashboard.isLoading}
            hasMatchesError={dashboard.isMatchesError}
            hasSavedJobsError={dashboard.isSavedJobsError}
          />
        </div>

        <div className="space-y-6 xl:col-span-4">
          <ResumeReadinessCard
            summary={data.resumeSummary}
            isLoading={dashboard.isLoading}
            hasError={dashboard.isResumesError}
          />
          <SkillsOverviewCard
            summary={data.skillsSummary}
            isLoading={dashboard.isLoading}
            hasError={dashboard.isSkillsError}
          />
          <QuickLinksCard />
        </div>
      </div>
    </div>
  )
}
