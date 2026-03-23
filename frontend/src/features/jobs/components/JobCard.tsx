import {
  MapPin,
  Clock,
  CircleCheck,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

import { Link, useSearchParams } from 'react-router-dom'

import type { Job, JobBriefInfo, UserJobMatch } from '@/types/job'
import { Badge } from '@/components/ui/badge'
import {
    Card,
    CardContent,
    CardHeader,
} from '@/components/ui/card'
import {
  formatJobCategory,
  getSourceMeta,
  JobSalaryDisplay,
} from '@/components/job/jobDisplay'

interface JobCardProps {
    job: Job | JobBriefInfo // Accept both full Job and JobBriefInfo
    matchData?: UserJobMatch // Optional match data for recommended view
    savedAt?: string | null
    onOpenJob?: (jobId: number) => void
    highlighted?: boolean
}

export function JobCard({ job, matchData, savedAt, onOpenJob, highlighted = false }: JobCardProps) {
    const [searchParams] = useSearchParams()
    const sourceMeta = getSourceMeta(job.source)
    const SourceIcon = sourceMeta.icon
    const categoryText = formatJobCategory(job)

    // Preserve current search params when navigating to detail page
    const detailUrl = `/jobs/${job.id}?${searchParams.toString()}`

    const isViewed = Boolean(job.is_viewed);

    return (
      <Card
        data-job-id={job.id}
        className={`relative hover:shadow-md transition-shadow border-slate-200 bg-white ${
          highlighted ? "ring-2 ring-amber-300 border-amber-300" : ""
        }`}
      >
        {/* Company logo - absolute positioned at Card level, independent of all content */}
        {job.company_logo && (
          <img
            src={job.company_logo}
            alt={`${job.advertiser_name} logo`}
            className="absolute top-4 right-4 h-20 w-auto max-w-[100px] object-contain rounded-md z-10"
          />
        )}

        <CardHeader className="p-4 pb-2 pr-28">
          <div className="space-y-1">
            {/* Match score - show if available */}
            {matchData && (
              <div className="flex items-center gap-3 text-sm mb-2">
                <span className="font-semibold text-indigo-600">
                  {Math.round(matchData.skill_match_score)}% Match
                </span>
                {matchData.resume_match_score !== null && (
                  <span className="text-slate-500 text-xs">
                    Resume: {Math.round(matchData.resume_match_score)}%
                  </span>
                )}
              </div>
            )}

            <div className="flex items-start gap-3">
              <Link
                to={detailUrl}
                className={`text-lg hover:text-indigo-600 line-clamp-2 ${
                  isViewed ? "font-medium text-slate-700" : "font-semibold text-slate-900"
                }`}
                onClick={() => onOpenJob?.(job.id)}
              >
                {job.title}
              </Link>
              {job.is_expired && (
                <Badge className="mt-0.5 bg-red-500 text-white hover:bg-red-600">Expired</Badge>
              )}
              {job.has_application && (
                <CircleCheck
                  className="mt-1 h-5 w-5 shrink-0 text-emerald-600"
                  aria-label="Added to applications"
                />
              )}
            </div>
            <div className="flex items-center gap-2 text-lg text-slate-600">
              {sourceMeta.iconSrc ? (
                <img
                  src={sourceMeta.iconSrc}
                  alt={`${sourceMeta.label} icon`}
                  className="h-5 w-5 rounded-sm object-contain"
                />
              ) : (
                SourceIcon && <SourceIcon className="h-5 w-5" />
              )}
              <span className="text-slate-500">{sourceMeta.label}</span>
              <span className="text-slate-300">|</span>
              <span className="font-medium">{job.advertiser_name}</span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 pt-2 space-y-3">
          <div className="flex flex-wrap gap-y-2 gap-x-4 text-sm text-slate-500">
            <div className="flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5" />
              <span>{job.location_label}</span>
            </div>
            <div className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              <span>{job.work_types_label}</span>
            </div>
            {job.salary_label && (
              <JobSalaryDisplay salaryLabel={job.salary_label} />
            )}
          </div>

          {job.abstract && (
            <p className="text-sm text-slate-600 line-clamp-2">
              {job.abstract}
            </p>
          )}

          <div className="flex flex-wrap gap-2 pt-1">
            {categoryText && (
              <span className="text-xs text-slate-500">{categoryText}</span>
            )}
            <span className="ml-auto whitespace-nowrap text-xs text-slate-400 flex items-center">
              {savedAt
                ? `saved ${formatDistanceToNow(new Date(savedAt), {
                    addSuffix: true,
                  })}`
                : isViewed && job.last_viewed_at
                ? `viewed ${formatDistanceToNow(new Date(job.last_viewed_at), {
                    addSuffix: true,
                  })}`
                : job.listed_at
                ? `Posted ${formatDistanceToNow(new Date(job.listed_at), {
                    addSuffix: true,
                  })}`
                : "Posted recently"}
            </span>
          </div>
        </CardContent>
      </Card>
    );
}

