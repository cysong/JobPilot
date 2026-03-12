import { MapPin, Building2, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

import { Link, useSearchParams } from 'react-router-dom'

import type { Job, JobBriefInfo, UserJobMatch } from '@/types/job'
import { Badge } from '@/components/ui/badge'
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
} from '@/components/ui/card'

interface JobCardProps {
    job: Job | JobBriefInfo // Accept both full Job and JobBriefInfo
    matchData?: UserJobMatch // Optional match data for recommended view
    savedAt?: string | null
    onOpenJob?: (jobId: number) => void
    highlighted?: boolean
}

const formatSourceLabel = (source: string | null | undefined): string =>
  source ? source.toUpperCase() : "UNKNOWN";

export function JobCard({ job, matchData, savedAt, onOpenJob, highlighted = false }: JobCardProps) {
    const [searchParams] = useSearchParams()

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
              <span
                className={`mt-2 h-2.5 w-2.5 rounded-full shrink-0 ${
                  isViewed ? "bg-slate-300" : "border border-indigo-500"
                }`}
                aria-label={isViewed ? "Viewed job" : "Unviewed job"}
                title={isViewed ? "Viewed" : "Unviewed"}
              />
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Building2 className="h-4 w-4" />
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
              <div className="flex items-center gap-1">
                <span>{job.salary_label}</span>
              </div>
            )}
          </div>

          {job.abstract && (
            <p className="text-sm text-slate-600 line-clamp-2">
              {job.abstract}
            </p>
          )}

          <div className="flex flex-wrap gap-2 pt-1">
            <Badge variant="outline" className="font-normal text-xs text-slate-500">
              {formatSourceLabel(job.source)}
            </Badge>
            {job.classification && (
              <Badge variant="secondary" className="font-normal text-xs">
                {job.classification}
              </Badge>
            )}
            {job.sub_classification && (
              <Badge
                variant="outline"
                className="font-normal text-xs text-slate-500"
              >
                {job.sub_classification}
              </Badge>
            )}
          </div>
        </CardContent>
        <CardFooter className={`p-4 pt-0 text-xs ${isViewed ? "text-slate-400" : "text-slate-500"}`}>
          <span>
            {savedAt
              ? `saved ${formatDistanceToNow(new Date(savedAt), {
                  addSuffix: true,
                })}`
              : isViewed && job.last_viewed_at
              ? `viewed ${formatDistanceToNow(new Date(job.last_viewed_at), {
                  addSuffix: true,
                })}`
              : job.listed_at
              ? formatDistanceToNow(new Date(job.listed_at), {
                  addSuffix: true,
                })
              : "recently"}
          </span>
        </CardFooter>
      </Card>
    );
}
