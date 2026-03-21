import { useEffect, useState } from 'react'
import { Loader2, Pencil, Search, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useTargetJobTitleOptions, useUpdateTargetJobTitles } from '@/features/resumes/hooks/useResumes'
import { cn } from '@/utils/cn'

interface TargetJobTitlesEditorProps {
  resumeId: string
  resumeTitle: string
  currentTitles: string[]
}

function hasTitle(titles: string[], title: string) {
  const normalizedTitle = title.trim().toLowerCase()
  return titles.some((item) => item.trim().toLowerCase() === normalizedTitle)
}

export function TargetJobTitlesEditor({
  resumeId,
  resumeTitle,
  currentTitles,
}: TargetJobTitlesEditorProps) {
  const [open, setOpen] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  const [selectedTitles, setSelectedTitles] = useState<string[]>(currentTitles)
  const updateTargetJobTitles = useUpdateTargetJobTitles()

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedKeyword(searchKeyword.trim())
    }, 300)

    return () => window.clearTimeout(timer)
  }, [searchKeyword])

  useEffect(() => {
    if (open) {
      setSelectedTitles(currentTitles)
      setSearchKeyword('')
      setDebouncedKeyword('')
    }
  }, [currentTitles, open])

  const { data, isFetching } = useTargetJobTitleOptions(debouncedKeyword, open)
  const options = data?.items ?? []
  const selectionLimit = data?.selection_limit
  const reachedLimit = selectionLimit !== undefined && selectedTitles.length >= selectionLimit

  const handleAdd = (title: string) => {
    if (hasTitle(selectedTitles, title) || reachedLimit) {
      return
    }

    setSelectedTitles((previous) => [...previous, title])
  }

  const handleRemove = (title: string) => {
    const normalizedTitle = title.trim().toLowerCase()
    setSelectedTitles((previous) =>
      previous.filter((item) => item.trim().toLowerCase() !== normalizedTitle),
    )
  }

  const handleSave = async () => {
    await updateTargetJobTitles.mutateAsync({
      id: resumeId,
      targetJobTitles: selectedTitles,
    })
    setOpen(false)
  }

  const triggerLabel = currentTitles.length > 0
    ? `Edit Roles (${currentTitles.length})`
    : 'Edit Roles'

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 border-slate-200 bg-white/90 text-slate-600 hover:bg-slate-50"
        >
          <Pencil className="h-3.5 w-3.5" />
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent
        className="max-w-2xl gap-0 overflow-hidden border-slate-200 p-0"
        onClick={(event) => event.stopPropagation()}
      >
        <DialogHeader className="border-b border-slate-200 px-6 py-5">
          <DialogTitle className="text-slate-900">Edit Target Roles</DialogTitle>
          <DialogDescription className="text-slate-500">
            {selectionLimit
              ? `Choose up to ${selectionLimit} target roles for ${resumeTitle}.`
              : `Choose target roles for ${resumeTitle}.`}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 px-6 py-5">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              value={searchKeyword}
              onChange={(event) => setSearchKeyword(event.target.value)}
              placeholder="Search target roles..."
              className="pl-9"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-700">Selected Roles</p>
              <p className="text-xs text-slate-500">
                {selectionLimit
                  ? `${selectedTitles.length}/${selectionLimit}`
                  : `${selectedTitles.length}`}
              </p>
            </div>
            <div className="min-h-[76px] rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-3">
              {selectedTitles.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                {selectedTitles.map((title) => (
                  <Badge
                    key={title}
                    variant="secondary"
                    className="gap-1 bg-slate-100 px-2.5 py-1 text-slate-700"
                  >
                    <span>{title}</span>
                    <button
                      type="button"
                      className="rounded-full text-slate-500 transition-colors hover:text-slate-900"
                      onClick={() => handleRemove(title)}
                    >
                      <X className="h-3 w-3" />
                      <span className="sr-only">Remove {title}</span>
                    </button>
                  </Badge>
                ))}
                </div>
              ) : (
                <div className="flex min-h-[48px] items-center text-sm text-slate-500">
                  No target roles selected yet.
                </div>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-700">
                {debouncedKeyword ? 'Matching Roles' : 'Top Roles'}
              </p>
              {isFetching && (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Loading
                </div>
              )}
            </div>

            <div className="min-h-[224px] rounded-lg border border-slate-200 bg-white px-3 py-3">
              {options.length > 0 ? (
                <div className="flex max-h-[200px] flex-wrap gap-2 overflow-y-auto pr-1">
                {options.map((option) => {
                  const isSelected = hasTitle(selectedTitles, option.title)
                  const disabled = isSelected || reachedLimit

                  return (
                    <button
                      key={option.title}
                      type="button"
                      onClick={() => handleAdd(option.title)}
                      disabled={disabled}
                      className={cn(
                        'rounded-full border px-3 py-1.5 text-sm transition-colors',
                        isSelected
                          ? 'border-slate-200 bg-slate-100 text-slate-400'
                          : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300 hover:bg-slate-100',
                        !isSelected && reachedLimit && 'cursor-not-allowed text-slate-400',
                      )}
                    >
                      {option.title} ({option.count})
                    </button>
                  )
                })}
                </div>
              ) : (
                <div className="flex min-h-[200px] items-center justify-center text-sm text-slate-500">
                  No matching roles found.
                </div>
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="border-t border-slate-200 px-6 py-4">
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={updateTargetJobTitles.isPending}
          >
            Cancel
          </Button>
          <Button
            className="bg-indigo-600 hover:bg-indigo-700"
            onClick={handleSave}
            disabled={updateTargetJobTitles.isPending}
          >
            {updateTargetJobTitles.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving
              </>
            ) : (
              'Save Roles'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
