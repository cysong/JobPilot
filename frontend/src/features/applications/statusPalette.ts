import type { ApplicationStatus } from '@/types/application'

export type StatusPaletteEntry = {
  /** Solid badge fill — bg + text + border-transparent. Used by ApplicationStatusBadge. */
  badgeClass: string
  /** Optional decoration applied alongside badgeClass (e.g. animate-pulse). */
  badgeExtraClass?: string
  /** Text-only color for inline labels. Used by TimelineCard entries. */
  textClass: string
  /** Soft pill (border + bg + text) for status-tinted chips. Used by Material State pills. */
  pillClass: string
}

export const STATUS_PALETTE: Record<ApplicationStatus, StatusPaletteEntry> = {
  PENDING: {
    badgeClass: 'border-transparent bg-slate-200 text-slate-700 hover:bg-slate-200',
    textClass: 'text-slate-500',
    pillClass: 'border-slate-200 bg-slate-50 text-slate-600',
  },
  TAILORING: {
    badgeClass: 'border-transparent bg-sky-500 text-white hover:bg-sky-600',
    badgeExtraClass: 'animate-pulse',
    textClass: 'text-sky-600',
    pillClass: 'border-sky-200 bg-sky-50 text-sky-700',
  },
  READY: {
    badgeClass: 'border-transparent bg-emerald-500 text-white hover:bg-emerald-600',
    textClass: 'text-emerald-600',
    pillClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  APPLIED: {
    badgeClass: 'border-transparent bg-indigo-500 text-white hover:bg-indigo-600',
    textClass: 'text-indigo-600',
    pillClass: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  },
  PHONE_SCREEN: {
    badgeClass: 'border-transparent bg-violet-500 text-white hover:bg-violet-600',
    textClass: 'text-violet-600',
    pillClass: 'border-violet-200 bg-violet-50 text-violet-700',
  },
  INTERVIEWING: {
    badgeClass: 'border-transparent bg-fuchsia-500 text-white hover:bg-fuchsia-600',
    textClass: 'text-fuchsia-600',
    pillClass: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700',
  },
  OFFER: {
    badgeClass: 'border-transparent bg-amber-400 text-slate-900 hover:bg-amber-500',
    textClass: 'text-amber-600',
    pillClass: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  REJECTED: {
    badgeClass: 'border-transparent bg-rose-500 text-white hover:bg-rose-600',
    textClass: 'text-rose-600',
    pillClass: 'border-rose-200 bg-rose-50 text-rose-700',
  },
  FAILED: {
    badgeClass: 'border-transparent bg-red-600 text-white hover:bg-red-700',
    textClass: 'text-red-600',
    pillClass: 'border-red-200 bg-red-50 text-red-700',
  },
}
