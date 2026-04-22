import { useEffect, useRef, useState } from 'react'
import { differenceInDays, formatDistanceToNow, parseISO } from 'date-fns'
import { Check, ChevronDown, ChevronUp, Pencil, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  useApplicationStatusHistory,
  useUpdateHistoryNote,
} from '@/features/applications/hooks/useApplicationHistory'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { STATUS_PALETTE } from '@/features/applications/statusPalette'
import type { ApplicationStatus, StatusHistoryEntry } from '@/types/application'
import { cn } from '@/utils/cn'

// Relative time for < 7 days, absolute otherwise
function formatEntryTime(iso: string): string {
  const date = parseISO(iso)
  if (differenceInDays(new Date(), date) < 7) {
    return formatDistanceToNow(date, { addSuffix: true })
  }
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const STATUS_LABEL: Record<string, string> = {
  PENDING: 'Pending',
  TAILORING: 'Tailoring',
  READY: 'Ready',
  APPLIED: 'Applied',
  PHONE_SCREEN: 'Phone Screen',
  INTERVIEWING: 'Interviewing',
  OFFER: 'Offer',
  REJECTED: 'Rejected',
  FAILED: 'Failed',
}

// ── Single entry row ────────────────────────────────────────────────────────

interface EntryRowProps {
  entry: StatusHistoryEntry
  isLatest?: boolean
  isEditing?: boolean
  noteText?: string
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>
  onNoteChange?: (v: string) => void
  onEditStart?: () => void
  onSave?: () => void
  onCancel?: () => void
  isSaving?: boolean
}

function EntryRow({
  entry,
  isLatest = false,
  isEditing = false,
  noteText = '',
  textareaRef,
  onNoteChange,
  onEditStart,
  onSave,
  onCancel,
  isSaving = false,
}: EntryRowProps) {
  const label = STATUS_LABEL[entry.to_status] ?? entry.to_status
  const color =
    STATUS_PALETTE[entry.to_status as ApplicationStatus]?.textClass ?? 'text-slate-600'
  const NOTE_LIMIT = 120
  const longNote = entry.note && entry.note.length > NOTE_LIMIT

  return (
    <div className="group relative space-y-1.5">
      {/* Status + time row */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className={`text-sm font-semibold ${color}`}>{label}</span>
            {isLatest && !isEditing && (
              <button
                onClick={onEditStart}
                className="invisible rounded p-0.5 text-slate-400 transition-colors hover:text-slate-600 group-hover:visible"
                title={entry.note ? 'Edit note' : 'Add note'}
              >
                <Pencil className="h-3 w-3" />
              </button>
            )}
          </div>
          <p className="text-xs text-slate-400">{formatEntryTime(entry.changed_at)}</p>
        </div>
      </div>

      {/* Note — truncated with tooltip on hover */}
      {!isEditing && entry.note && (
        <p
          className="line-clamp-2 cursor-default text-xs text-slate-600"
          title={longNote ? entry.note : undefined}
        >
          {entry.note}
        </p>
      )}

      {/* Inline note editor (latest entry only) */}
      {isEditing && (
        <div className="space-y-2">
          <Textarea
            ref={textareaRef}
            value={noteText}
            onChange={(e) => onNoteChange?.(e.target.value)}
            placeholder="What happened? e.g. HR called, 30 min screen…"
            className="min-h-[72px] resize-none text-xs"
            onKeyDown={(e) => {
              if (e.key === 'Escape') onCancel?.()
            }}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onCancel}
              disabled={isSaving}
              className="h-7 text-xs"
            >
              <X className="mr-1 h-3 w-3" />
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={onSave}
              disabled={isSaving || !noteText.trim()}
              className="h-7 text-xs"
            >
              <Check className="mr-1 h-3 w-3" />
              {isSaving ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── TimelineCard ────────────────────────────────────────────────────────────

interface TimelineCardProps {
  applicationId: string
  /** Set to true by parent after a status change to auto-open note editor */
  forceEditLatest?: boolean
  onForceEditLatestConsumed?: () => void
}

export function TimelineCard({
  applicationId,
  forceEditLatest,
  onForceEditLatestConsumed,
}: TimelineCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [isEditingLatest, setIsEditingLatest] = useState(false)
  const [noteText, setNoteText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Tracks the latest entry id we last saw, to detect new entries after status change
  const pendingEditRef = useRef(false)
  const lastLatestIdRef = useRef<string | null>(null)

  const { data, isLoading, isError } = useApplicationStatusHistory(applicationId)
  const updateNote = useUpdateHistoryNote(applicationId)

  const entries: StatusHistoryEntry[] = data?.items ?? []
  const latestEntry = entries[0] ?? null
  const olderEntries = entries.slice(1)

  // When parent signals a status change, set the pending flag and consume the signal
  useEffect(() => {
    if (forceEditLatest) {
      pendingEditRef.current = true
      onForceEditLatestConsumed?.()
    }
  }, [forceEditLatest, onForceEditLatestConsumed])

  // Open editor when a new (different) latest entry appears and pendingEdit is set
  useEffect(() => {
    if (!latestEntry) return
    if (pendingEditRef.current && latestEntry.id !== lastLatestIdRef.current) {
      pendingEditRef.current = false
      lastLatestIdRef.current = latestEntry.id
      setNoteText(latestEntry.note ?? '')
      setIsEditingLatest(true)
    } else {
      lastLatestIdRef.current = latestEntry.id
    }
  }, [latestEntry])

  // Auto-focus textarea once editing opens
  useEffect(() => {
    if (isEditingLatest) {
      const t = setTimeout(() => textareaRef.current?.focus(), 50)
      return () => clearTimeout(t)
    }
  }, [isEditingLatest])

  const startEdit = () => {
    if (!latestEntry) return
    setNoteText(latestEntry.note ?? '')
    setIsEditingLatest(true)
  }

  const cancelEdit = () => {
    setIsEditingLatest(false)
    setNoteText('')
  }

  const saveNote = () => {
    if (!latestEntry || !noteText.trim()) {
      cancelEdit()
      return
    }
    updateNote.mutate(
      { historyId: latestEntry.id, note: noteText.trim() },
      { onSuccess: () => setIsEditingLatest(false) },
    )
  }

  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Timeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {!isLoading && isError && (
          <Alert variant="destructive">
            <AlertTitle>Unable to load timeline</AlertTitle>
            <AlertDescription>Please try again later.</AlertDescription>
          </Alert>
        )}

        {!isLoading && !isError && entries.length === 0 && (
          <p className="text-sm text-slate-500">No status history yet.</p>
        )}

        {/* Entries flow as a single uniform list; older ones collapsed by default */}
        {(expanded ? entries : entries.slice(0, 1)).map((entry, i) => {
          const isLatest = i === 0
          return (
            <EntryRow
              key={entry.id}
              entry={entry}
              isLatest={isLatest}
              isEditing={isLatest && isEditingLatest}
              noteText={isLatest ? noteText : undefined}
              textareaRef={isLatest ? textareaRef : undefined}
              onNoteChange={isLatest ? setNoteText : undefined}
              onEditStart={isLatest ? startEdit : undefined}
              onSave={isLatest ? saveNote : undefined}
              onCancel={isLatest ? cancelEdit : undefined}
              isSaving={isLatest && updateNote.isPending}
            />
          )
        })}

        {olderEntries.length > 0 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className={cn(
              'flex w-full items-center justify-center gap-1 text-xs text-slate-400 transition-colors hover:text-slate-600',
              // Subtle fold-line above the button while collapsed hints at hidden entries.
              !expanded && 'border-t border-dashed border-slate-200 pt-2',
              expanded && 'pt-1',
            )}
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                Collapse
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                {olderEntries.length} earlier {olderEntries.length === 1 ? 'entry' : 'entries'}
              </>
            )}
          </button>
        )}
      </CardContent>
    </Card>
  )
}
