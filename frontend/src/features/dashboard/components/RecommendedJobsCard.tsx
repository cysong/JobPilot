import { formatDistanceToNow } from 'date-fns'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Sparkles, Star } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { UserJobMatch } from '@/types/job'

interface RecommendedJobsCardProps {
  recommendedJobs: UserJobMatch[]
  savedJobs: UserJobMatch[]
  isLoading: boolean
  hasMatchesError: boolean
  hasSavedJobsError: boolean
}

const getCompanyName = (job: UserJobMatch['job']) => job.advertiser_name || 'Unknown Company'

function MatchList({
  items,
  mode,
}: {
  items: UserJobMatch[]
  mode: 'matches' | 'saved'
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
        {mode === 'matches'
          ? 'No strong matches yet. Browse jobs and strengthen resumes or skills to improve matching.'
          : 'No saved jobs yet. Save interesting jobs from the listings page.'}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex flex-col gap-4 rounded-2xl border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between"
        >
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Link to={`/jobs/${item.job.id}`} className="font-semibold text-slate-900 hover:text-indigo-600">
                {item.job.title}
              </Link>
              {mode === 'matches' ? (
                <Badge className="bg-indigo-600 text-white hover:bg-indigo-700">
                  {Math.round(item.skill_match_score)}% match
                </Badge>
              ) : null}
              {item.job.has_application ? (
                <Badge variant="outline" className="border-emerald-200 text-emerald-700">
                  In applications
                </Badge>
              ) : null}
              {item.job.is_expired ? <Badge className="bg-red-500 text-white hover:bg-red-600">Expired</Badge> : null}
            </div>
            <div className="text-sm text-slate-600">
              {getCompanyName(item.job)}
              {item.job.location_label ? ` · ${item.job.location_label}` : ''}
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
              {item.recommended_resume ? (
                <span>Recommended resume: {item.recommended_resume.title}</span>
              ) : mode === 'saved' ? (
                <span>Saved for later review</span>
              ) : null}
              <span>
                {mode === 'saved' ? 'Saved' : 'Matched'}{' '}
                {formatDistanceToNow(new Date(item.calculated_at), { addSuffix: true })}
              </span>
            </div>
          </div>

          <Button asChild size="sm" variant="outline">
            <Link to={`/jobs/${item.job.id}`}>
              View Job
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      ))}
    </div>
  )
}

export function RecommendedJobsCard({
  recommendedJobs,
  savedJobs,
  isLoading,
  hasMatchesError,
  hasSavedJobsError,
}: RecommendedJobsCardProps) {
  if (isLoading) {
    return <Skeleton className="h-[28rem] w-full rounded-3xl" />
  }

  return (
    <Card className="rounded-3xl border-slate-200 shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-slate-500">Opportunities</div>
          <CardTitle className="text-xl text-slate-950">Recommended Jobs</CardTitle>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/jobs">
            Browse Jobs
            <ArrowUpRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs defaultValue="matches" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="matches">
              <Sparkles className="mr-2 h-4 w-4" />
              Best Matches
            </TabsTrigger>
            <TabsTrigger value="saved">
              <Star className="mr-2 h-4 w-4" />
              Saved Jobs
            </TabsTrigger>
          </TabsList>

          <TabsContent value="matches" className="space-y-3">
            {hasMatchesError ? (
              <div className="rounded-2xl border border-dashed border-red-200 bg-red-50 p-4 text-sm text-red-700">
                Failed to load job matches. You can still browse jobs directly.
              </div>
            ) : null}
            <MatchList items={recommendedJobs} mode="matches" />
          </TabsContent>

          <TabsContent value="saved" className="space-y-3">
            {hasSavedJobsError ? (
              <div className="rounded-2xl border border-dashed border-red-200 bg-red-50 p-4 text-sm text-red-700">
                Failed to load saved jobs. Open Jobs to restore the list.
              </div>
            ) : null}
            <MatchList items={savedJobs} mode="saved" />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
