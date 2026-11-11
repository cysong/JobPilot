import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, CircleDashed, Info, XCircle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { useJobMatchDetail } from '@/features/jobs/hooks/useJobs'
import type { MatchConditionCheck, MatchDetail, MatchTechItem } from '@/types/job'
import { cn } from '@/utils/cn'

import { MatchBadges } from './MatchBadges'

const RELATION_META: Record<MatchTechItem['relation'], { label: string; className: string }> = {
  same: { label: 'Have it', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  substitute: { label: 'Similar', className: 'border-sky-200 bg-sky-50 text-sky-700' },
  missing: { label: 'Missing', className: 'border-red-200 bg-red-50 text-red-700' },
}

const LEVEL_LABEL: Record<string, string> = {
  strong: 'Strong',
  partial: 'Partial',
  weak: 'Weak',
  none: 'None',
}

const TIER_ADJUSTMENT_LABEL: Record<string, string> = {
  people_management_required: 'needs people management experience',
  adjacent_family: 'adjacent role family',
}

const formatYears = (value: number | null) => (value === null ? '—' : `${Math.round(value * 10) / 10} yrs`)

function ConditionRow({ label, check }: { label: string; check: MatchConditionCheck | null }) {
  if (!check) return null
  // Language checks carry required_languages; the other checks carry a requirement code.
  const stated = check.required_languages
    ? check.required_languages.length > 0
    : Boolean(check.requirement) && check.requirement !== 'none'
  if (!stated) return null
  const Icon = check.satisfied === false ? XCircle : check.satisfied === true ? CheckCircle2 : CircleDashed
  const tone =
    check.satisfied === false ? 'text-red-600' : check.satisfied === true ? 'text-emerald-600' : 'text-slate-400'
  const requirement = check.required_languages?.length
    ? check.required_languages.join(', ')
    : [check.requirement?.replace(/_/g, ' '), check.country].filter(Boolean).join(' · ')
  return (
    <li className="flex gap-2 text-sm">
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', tone)} />
      <div>
        <span className="font-medium text-slate-800">{label}:</span>{' '}
        <span className="text-slate-700">{requirement}</span>
        {check.quote ? <p className="text-xs text-slate-500">“{check.quote}”</p> : null}
      </div>
    </li>
  )
}

function MatchDetailBody({ detail, actions }: { detail: MatchDetail; actions?: ReactNode }) {
  const coreItems = detail.tech_items.filter((item) => item.is_core)
  const otherItems = detail.tech_items.filter((item) => !item.is_core)
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <MatchBadges match={detail} />
          {actions}
        </div>
        {detail.status === 'rejected' ? (
          <p className="text-sm text-red-700">
            {detail.reject_reason}
            {detail.reject_quote ? <span className="text-slate-500"> “{detail.reject_quote}”</span> : null}
          </p>
        ) : null}
        {detail.tier_reason ? <p className="text-sm text-slate-700">{detail.tier_reason}</p> : null}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          {detail.recommended_resume ? <span>Recommended resume: {detail.recommended_resume.title}</span> : null}
          {detail.tech_level ? <span>Tech: {LEVEL_LABEL[detail.tech_level]}</span> : null}
          {detail.experience_level ? <span>Experience: {LEVEL_LABEL[detail.experience_level]}</span> : null}
          <span>
            Relevant {formatYears(detail.relevant_years)} / required {formatYears(detail.required_years)}
          </span>
          {detail.seniority_mismatch ? <span className="text-amber-700">Seniority mismatch</span> : null}
          {detail.people_management?.required && !detail.people_management.candidate_has ? (
            <span className="text-amber-700">People management required</span>
          ) : null}
          {detail.tier_adjustments?.length && detail.llm_tier ? (
            <span title={detail.tier_adjustments.map((r) => TIER_ADJUSTMENT_LABEL[r] ?? r).join('; ')}>
              Lowered from {detail.llm_tier}: {detail.tier_adjustments.map((r) => TIER_ADJUSTMENT_LABEL[r] ?? r).join(', ')}
            </span>
          ) : null}
        </div>
      </div>

      {detail.other_listings?.length ? (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-slate-900">Same job, other listings</h3>
          <ul className="space-y-1 text-sm">
            {detail.other_listings.map((listing) => (
              <li key={listing.job_id}>
                <Link to={`/jobs/${listing.job_id}`} className="text-indigo-600 hover:underline">
                  {listing.location_label ?? 'Unknown location'}
                </Link>
                {listing.source ? <span className="text-slate-500"> · {listing.source}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {detail.tech_items.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900">Requirements vs your resume</h3>
          <ul className="space-y-2">
            {[...coreItems, ...otherItems].map((item, index) => (
              <li key={`${item.requirement}-${index}`} className="flex gap-3 text-sm">
                <Badge variant="outline" className={cn('h-6 shrink-0', RELATION_META[item.relation].className)}>
                  {RELATION_META[item.relation].label}
                </Badge>
                <div className="min-w-0">
                  <p className={cn('text-slate-800', item.is_core && 'font-medium')}>
                    {item.requirement}
                    {item.is_core ? <span className="ml-2 text-xs font-normal text-indigo-600">core</span> : null}
                  </p>
                  {item.evidence.resume_quote ? (
                    <p className="text-xs text-slate-500">Resume: “{item.evidence.resume_quote}”</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {detail.experience_evidence.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900">Experience evidence</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {detail.experience_evidence.map((evidence, index) => (
              <li key={index}>{evidence.resume_quote || evidence.job_quote}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <ul className="space-y-2">
        <ConditionRow label="Work rights" check={detail.work_rights} />
        <ConditionRow label="Security clearance" check={detail.security_clearance} />
        <ConditionRow label="Work location" check={detail.work_location} />
        <ConditionRow label="Languages" check={detail.languages} />
      </ul>

      {detail.other_constraints.length > 0 ? (
        <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-900">
            <AlertTriangle className="h-4 w-4" />
            Other requirements to check
          </h3>
          <ul className="space-y-1 text-sm text-amber-900">
            {detail.other_constraints.map((constraint, index) => (
              <li key={index}>
                {constraint.requirement}
                <span className="text-xs text-amber-700"> “{constraint.quote}”</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

interface MatchResultPanelProps {
  jobId: number
  /** Optional controls (admin labeling) rendered next to the badges. */
  renderActions?: (detail: MatchDetail | null) => ReactNode
}

/** Matching v3 result for the current user on a job; nothing when there is none. */
export function MatchResultPanel({ jobId, renderActions }: MatchResultPanelProps) {
  const { data: detail, isLoading } = useJobMatchDetail(jobId)
  const actions = renderActions?.(detail ?? null)
  if (isLoading) return null
  if (!detail) {
    return actions ? (
      <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">
        <span className="flex items-center gap-2">
          <Info className="h-4 w-4" />
          No match result for this job.
        </span>
        {actions}
      </div>
    ) : null
  }
  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
      <h2 className="text-lg font-semibold text-slate-900">Match result</h2>
      <MatchDetailBody detail={detail} actions={actions} />
    </div>
  )
}
