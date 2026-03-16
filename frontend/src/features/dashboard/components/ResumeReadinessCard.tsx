import { format } from 'date-fns'
import { Link } from 'react-router-dom'
import { ArrowUpRight, FileCheck2, FilePenLine, UserRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardResumeSummary } from '@/features/dashboard/types'

interface ResumeReadinessCardProps {
  summary: DashboardResumeSummary
  isLoading: boolean
  hasError: boolean
}

export function ResumeReadinessCard({ summary, isLoading, hasError }: ResumeReadinessCardProps) {
  if (isLoading) {
    return <Skeleton className="h-72 w-full rounded-3xl" />
  }

  return (
    <Card className="rounded-3xl border-slate-200 shadow-sm">
      <CardHeader>
        <div className="text-sm font-medium text-slate-500">Resume Readiness</div>
        <CardTitle className="text-xl text-slate-950">Application Assets</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {hasError ? (
          <div className="rounded-2xl border border-dashed border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load resume data. Open the resumes page to retry.
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
              <FileCheck2 className="h-4 w-4" />
              Finalized
            </div>
            <div className="mt-2 text-3xl font-bold text-slate-950">{summary.finalizedCount}</div>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-amber-700">
              <FilePenLine className="h-4 w-4" />
              Drafts
            </div>
            <div className="mt-2 text-3xl font-bold text-slate-950">{summary.draftCount}</div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          {summary.latestResume ? (
            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-900">{summary.latestResume.title}</div>
              <div className="text-sm text-slate-600">
                {summary.latestResume.is_draft ? 'Draft resume' : 'Finalized resume'}
              </div>
              <div className="text-xs text-slate-500">
                Updated {format(new Date(summary.latestResume.updated_at), 'MMM d, yyyy')}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-900">No resumes yet</div>
              <div className="text-sm text-slate-600">
                Create a resume template to support matching and applications.
              </div>
            </div>
          )}
        </div>

        <Button asChild className="w-full">
          <Link to="/resumes">
            <UserRound className="mr-2 h-4 w-4" />
            Manage Resumes
            <ArrowUpRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}
