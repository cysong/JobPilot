import { Ban, MapPinOff } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { MatchSummary, MatchTier } from '@/types/job'

export const TIER_META: Record<MatchTier, { label: string; className: string }> = {
  A: { label: 'Strong match', className: 'bg-emerald-600 text-white hover:bg-emerald-600' },
  B: { label: 'Worth a try', className: 'bg-sky-600 text-white hover:bg-sky-600' },
  C: { label: 'Not recommended', className: 'bg-amber-500 text-white hover:bg-amber-500' },
  D: { label: 'Not relevant', className: 'bg-slate-500 text-white hover:bg-slate-500' },
}

const REJECT_LABELS: Record<string, string> = {
  LOCATION: 'Outside your locations',
  WORK_RIGHTS: 'Work rights',
  SECURITY_CLEARANCE: 'Security clearance',
  WORK_LOCATION: 'Work in another country',
  LANGUAGE: 'Language',
}

export const rejectLabel = (code: string | null) => (code ? REJECT_LABELS[code] ?? code : 'Rejected')

export function TierBadge({ tier }: { tier: MatchTier }) {
  const meta = TIER_META[tier]
  return (
    <Badge className={meta.className}>
      {tier} · {meta.label}
    </Badge>
  )
}

/** Tier (or rejection) badge plus the location note, as shown on job cards. */
export function MatchBadges({ match }: { match: MatchSummary }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {match.status === 'rejected' ? (
        <Badge className="gap-1 bg-red-600 text-white hover:bg-red-600">
          <Ban className="h-3 w-3" />
          Rejected · {rejectLabel(match.reject_code)}
        </Badge>
      ) : match.tier ? (
        <TierBadge tier={match.tier} />
      ) : null}
      {match.location_check === 'unknown' ? (
        <Badge variant="outline" className="gap-1 border-amber-300 text-amber-700">
          <MapPinOff className="h-3 w-3" />
          Location unconfirmed
        </Badge>
      ) : null}
    </div>
  )
}
