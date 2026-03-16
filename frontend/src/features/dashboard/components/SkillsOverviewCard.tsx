import { Link } from 'react-router-dom'
import { ArrowUpRight, Award } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardSkillsSummary } from '@/features/dashboard/types'

interface SkillsOverviewCardProps {
  summary: DashboardSkillsSummary
  isLoading: boolean
  hasError: boolean
}

export function SkillsOverviewCard({ summary, isLoading, hasError }: SkillsOverviewCardProps) {
  if (isLoading) {
    return <Skeleton className="h-80 w-full rounded-3xl" />
  }

  return (
    <Card className="rounded-3xl border-slate-200 shadow-sm">
      <CardHeader>
        <div className="text-sm font-medium text-slate-500">Skills Library</div>
        <CardTitle className="text-xl text-slate-950">Matching Foundation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {hasError ? (
          <div className="rounded-2xl border border-dashed border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load skill data. Open Skills to retry.
          </div>
        ) : null}

        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <div className="text-2xl font-bold text-slate-950">{summary.total}</div>
            <div className="text-xs text-slate-500">Total</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <div className="text-2xl font-bold text-slate-950">{summary.manualCount}</div>
            <div className="text-xs text-slate-500">Manual</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <div className="text-2xl font-bold text-slate-950">{summary.autoCount}</div>
            <div className="text-xs text-slate-500">Synced</div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium text-slate-700">Top skills</div>
          {summary.topSkills.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {summary.topSkills.map((skill) => (
                <span
                  key={skill.id}
                  className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700"
                >
                  {skill.skill_name}
                </span>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">
              No skills yet. Sync them from resumes or add them manually to improve matching.
            </div>
          )}
        </div>

        <Button asChild variant="outline" className="w-full">
          <Link to="/skills">
            <Award className="mr-2 h-4 w-4" />
            Manage Skills
            <ArrowUpRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}
