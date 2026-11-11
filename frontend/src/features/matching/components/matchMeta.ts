import type { MatchTier } from '@/types/job'

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
  NOT_EMPLOYMENT: 'Not an employment role',
}

export const rejectLabel = (code: string | null) => (code ? REJECT_LABELS[code] ?? code : 'Rejected')
