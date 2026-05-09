import { useState } from "react"
import { Link } from "react-router-dom"
import { CheckCircle2, Info, AlertCircle, Loader2 } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { jobsApi } from "@/api/jobs"
import { ApiError } from "@/types/api"
import type { EnqueueJobResponse } from "@/types/job"

type ResultEntry =
  | {
      kind: "enqueued"
      source?: string | null
      source_id?: string | null
    }
  | {
      kind: "exists"
      source?: string | null
      source_id?: string | null
      existing_job_id?: number | null
    }
  | {
      kind: "bad_request"
      message: string
    }
  | {
      kind: "unavailable"
    }

interface EnqueueJobDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const URL_REGEX = /^https?:\/\/.+/i
const MAX_RESULTS = 5

export function EnqueueJobDialog({ open, onOpenChange }: EnqueueJobDialogProps) {
  const [url, setUrl] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<ResultEntry[]>([])

  const isValid = URL_REGEX.test(url.trim())
  const canSubmit = !submitting && isValid

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return

    setSubmitting(true)
    try {
      const data: EnqueueJobResponse = await jobsApi.enqueueJobUrl(url.trim())
      const entry: ResultEntry =
        data.enqueued
          ? {
              kind: "enqueued",
              source: data.source,
              source_id: data.source_id,
            }
          : data.reason === "already_in_db"
            ? {
                kind: "exists",
                source: data.source,
                source_id: data.source_id,
                existing_job_id: data.existing_job_id ?? null,
              }
            : {
                // Unknown 200 shape (e.g. enqueued=false with no reason) —
                // surface as info row without a "view job" link.
                kind: "exists",
                source: data.source,
                source_id: data.source_id,
                existing_job_id: null,
              }
      setResults((prev) => [entry, ...prev].slice(0, MAX_RESULTS))
      setUrl("")
    } catch (err) {
      const entry: ResultEntry =
        err instanceof ApiError && err.status === 400
          ? { kind: "bad_request", message: err.message }
          : { kind: "unavailable" }
      setResults((prev) => [entry, ...prev].slice(0, MAX_RESULTS))
      // Keep `url` in the input on error so user can edit & retry.
    } finally {
      setSubmitting(false)
    }
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setUrl("")
      setResults([])
    }
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Job by URL</DialogTitle>
          <DialogDescription>
            手动提交一个岗位 URL，系统会调用爬虫将其加入队列。
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <Input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.seek.co.nz/job/82345678"
            disabled={submitting}
            autoFocus
          />
          <div className="flex justify-end">
            <Button type="submit" disabled={!canSubmit}>
              {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Submit
            </Button>
          </div>
        </form>

        {results.length > 0 && (
          <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
            {results.map((r, i) => (
              <ResultRow key={i} entry={r} />
            ))}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ResultRow({ entry }: { entry: ResultEntry }) {
  switch (entry.kind) {
    case "enqueued":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">
          <CheckCircle2 className="h-4 w-4" />
          <span>
            已加入抓取队列{" "}
            <span className="font-mono text-xs">
              {entry.source}/{entry.source_id}
            </span>
          </span>
        </div>
      )
    case "exists":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sky-800">
          <Info className="h-4 w-4" />
          <span>
            已存在{" "}
            <span className="font-mono text-xs">
              {entry.source}/{entry.source_id}
            </span>
          </span>
          {entry.existing_job_id != null && (
            <Link
              to={`/jobs/${entry.existing_job_id}`}
              className="ml-auto text-indigo-600 underline"
            >
              查看岗位
            </Link>
          )}
        </div>
      )
    case "bad_request":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">
          <AlertCircle className="h-4 w-4" />
          <span>{entry.message}</span>
        </div>
      )
    case "unavailable":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">
          <AlertCircle className="h-4 w-4" />
          <span>服务暂不可用，请稍后再试</span>
        </div>
      )
  }
}
