import { Ban, Copy, MapPinOff } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { MatchSummary, MatchTier } from '@/types/job'

import { rejectLabel, TIER_META } from './matchMeta'

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
      {match.other_listing_count ? (
        <Badge variant="outline" className="gap-1 text-slate-600" title="Same job posted in other cities or on other sites">
          <Copy className="h-3 w-3" />
          +{match.other_listing_count} other listing{match.other_listing_count > 1 ? 's' : ''}
        </Badge>
      ) : null}
    </div>
  )
}
