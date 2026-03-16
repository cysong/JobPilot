import { formatDistanceToNow } from 'date-fns'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ExternalLink } from 'lucide-react'

import { ApplicationStatusBadge } from '@/features/applications/components/ApplicationStatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardApplicationSnapshot } from '@/features/dashboard/types'

interface ApplicationPipelineCardProps {
  data: DashboardApplicationSnapshot
  isLoading: boolean
  hasError: boolean
}

export function ApplicationPipelineCard({ data, isLoading, hasError }: ApplicationPipelineCardProps) {
  if (isLoading) {
    return <Skeleton className="h-[30rem] w-full rounded-3xl" />
  }

  return (
    <Card className="rounded-3xl border-slate-200 shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-slate-500">Applications</div>
          <CardTitle className="text-xl text-slate-950">Pipeline Snapshot</CardTitle>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/applications">
            Open Applications
            <ArrowUpRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {hasError ? (
          <div className="rounded-2xl border border-dashed border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load application data. Open the full applications page to retry.
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm text-slate-500">Preparing</div>
            <div className="mt-2 text-2xl font-bold text-slate-950">
              {data.counts.Pending + data.counts.Tailoring}
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm text-slate-500">Ready</div>
            <div className="mt-2 text-2xl font-bold text-slate-950">{data.counts.Ready}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm text-slate-500">Applied</div>
            <div className="mt-2 text-2xl font-bold text-slate-950">{data.counts.Applied}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm text-slate-500">Interviewing</div>
            <div className="mt-2 text-2xl font-bold text-slate-950">{data.counts.Interviewing}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm text-slate-500">Offer</div>
            <div className="mt-2 text-2xl font-bold text-slate-950">{data.counts.Offer}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm text-slate-500">Rejected</div>
            <div className="mt-2 text-2xl font-bold text-slate-950">{data.counts.Rejected}</div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium text-slate-500">Needs attention</div>
          {data.attentionItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
              No active applications right now. Start from matched jobs or browse fresh listings.
            </div>
          ) : (
            <div className="space-y-3">
              {data.attentionItems.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-col gap-4 rounded-2xl border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between"
                >
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link to={item.href} className="font-semibold text-slate-900 hover:text-indigo-600">
                        {item.title}
                      </Link>
                      <ApplicationStatusBadge status={item.status} />
                      {item.isExpired ? <Badge className="bg-red-500 text-white hover:bg-red-600">Expired</Badge> : null}
                    </div>
                    <div className="text-sm text-slate-600">{item.company}</div>
                    <div className="text-xs text-slate-500">
                      Added {formatDistanceToNow(new Date(item.addedAt), { addSuffix: true })}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button asChild size="sm" variant={item.actionLabel === 'View Application' ? 'outline' : 'default'}>
                      {item.actionExternal ? (
                        <a href={item.actionHref} target="_blank" rel="noopener noreferrer">
                          {item.actionLabel}
                          <ExternalLink className="ml-2 h-4 w-4" />
                        </a>
                      ) : (
                        <Link to={item.actionHref}>
                          {item.actionLabel}
                          <ArrowUpRight className="ml-2 h-4 w-4" />
                        </Link>
                      )}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
