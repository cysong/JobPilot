import { Ban, Hourglass } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/utils/cn'
import type { MatchCounts, MatchTier, MatchView } from '@/types/job'

import { TIER_META } from './matchMeta'

const FILTER_TIERS = ['A', 'B', 'C'] as const satisfies readonly MatchTier[]

interface MatchFilterBarProps {
  matchView: MatchView
  matchTiers: MatchTier[]
  counts?: MatchCounts
  onViewChange: (view: MatchView) => void
  onTierToggle: (tier: MatchTier) => void
}

export function MatchFilterBar({ matchView, matchTiers, counts, onViewChange, onTierToggle }: MatchFilterBarProps) {
  const isRejected = matchView === 'rejected'
  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      {FILTER_TIERS.map((tier) => {
        const active = !isRejected && matchTiers.includes(tier)
        return (
          <Button
            key={tier}
            type="button"
            size="sm"
            variant="outline"
            aria-pressed={active}
            onClick={() => (isRejected ? onViewChange('recommended') : onTierToggle(tier))}
            className={cn('gap-2', active && TIER_META[tier].className)}
          >
            {tier} · {TIER_META[tier].label}
            {counts ? <span className="text-xs opacity-80">{counts[tier]}</span> : null}
          </Button>
        )
      })}
      <Button
        type="button"
        size="sm"
        variant="outline"
        aria-pressed={isRejected}
        onClick={() => onViewChange(isRejected ? 'recommended' : 'rejected')}
        className={cn('gap-2', isRejected && 'bg-red-600 text-white hover:bg-red-700 hover:text-white')}
      >
        <Ban className="h-3.5 w-3.5" />
        Rejected
        {counts ? <span className="text-xs opacity-80">{counts.rejected}</span> : null}
      </Button>
      {counts && counts.pending > 0 ? (
        <span className="ml-auto flex items-center gap-1 text-xs text-slate-500">
          <Hourglass className="h-3.5 w-3.5" />
          {counts.pending} jobs waiting to be matched
        </span>
      ) : null}
    </div>
  )
}
