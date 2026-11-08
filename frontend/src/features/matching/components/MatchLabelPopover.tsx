import { useState } from 'react'
import { Loader2, Tag } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Textarea } from '@/components/ui/textarea'
import { useCreateMatchLabel } from '@/features/matching/hooks/useMatching'
import { useAuthStore } from '@/store/authStore'
import { Role } from '@/types/auth'
import type { MatchLabelInfo } from '@/types/job'
import { MATCH_REASON_TAGS, type MatchLabelValue, type MatchReasonTag } from '@/types/matching'
import { cn } from '@/utils/cn'

const LABELS: { value: MatchLabelValue; hint: string }[] = [
  { value: 'A', hint: 'Tech and experience match' },
  { value: 'B', hint: 'Worth a try' },
  { value: 'C', hint: 'Not recommended' },
  { value: 'D', hint: 'Different track' },
  { value: 'REJECT', hint: 'Hard condition unmet' },
]

interface MatchLabelPopoverProps {
  jobId: number
  current: MatchLabelInfo | null
  /** Shown for jobs without a match result: the label then means "should have matched". */
  noResult?: boolean
}

/** Admin-only: label the system result for a job (append-only on the server). */
export function MatchLabelPopover({ jobId, current, noResult = false }: MatchLabelPopoverProps) {
  const isAdmin = useAuthStore((state) => state.user?.role === Role.ADMIN)
  const [open, setOpen] = useState(false)
  const [label, setLabel] = useState<MatchLabelValue | null>(null)
  const [tags, setTags] = useState<MatchReasonTag[]>([])
  const [note, setNote] = useState('')
  const createLabel = useCreateMatchLabel()

  if (!isAdmin) return null

  const handleOpenChange = (next: boolean) => {
    if (next) {
      setLabel((current?.label as MatchLabelValue | undefined) ?? null)
      setTags((current?.reason_tags as MatchReasonTag[] | undefined) ?? [])
      setNote(current?.note ?? '')
    }
    setOpen(next)
  }

  const toggleTag = (tag: MatchReasonTag) =>
    setTags((prev) => (prev.includes(tag) ? prev.filter((item) => item !== tag) : [...prev, tag]))

  const handleSave = () => {
    if (!label) return
    createLabel.mutate(
      { job_id: jobId, label, reason_tags: tags, note: note.trim() || null },
      { onSuccess: () => setOpen(false) },
    )
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={cn('h-6 gap-1 px-2 text-xs', current && 'border-violet-300 text-violet-700')}
          onClick={(event) => event.stopPropagation()}
        >
          <Tag className="h-3 w-3" />
          {current ? `Labeled ${current.label}` : noResult ? 'Should match?' : 'Label'}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 space-y-4" align="start" onClick={(event) => event.stopPropagation()}>
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-900">
            {noResult ? 'This job has no match result. What should it be?' : 'Correct tier'}
          </p>
          <div className="grid grid-cols-5 gap-1">
            {LABELS.map((item) => (
              <Button
                key={item.value}
                type="button"
                size="sm"
                variant={label === item.value ? 'default' : 'outline'}
                title={item.hint}
                className="px-0 text-xs"
                onClick={() => setLabel(item.value)}
              >
                {item.value === 'REJECT' ? 'Reject' : item.value}
              </Button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-900">What was wrong</p>
          <div className="flex flex-wrap gap-1">
            {MATCH_REASON_TAGS.map((tag) => (
              <Button
                key={tag}
                type="button"
                size="sm"
                variant={tags.includes(tag) ? 'secondary' : 'ghost'}
                className={cn('h-6 px-2 text-xs', tags.includes(tag) && 'bg-violet-100 text-violet-800')}
                onClick={() => toggleTag(tag)}
              >
                {tag.toLowerCase()}
              </Button>
            ))}
          </div>
        </div>
        <Textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Note (optional)"
          rows={2}
          maxLength={2000}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button type="button" size="sm" disabled={!label || createLabel.isPending} onClick={handleSave}>
            {createLabel.isPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            Save label
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
