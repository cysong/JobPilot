import { useEffect, useState } from 'react'
import { formatDistanceToNow } from 'date-fns'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useRoleFamilies,
  useTitleFamilies,
  useUpdateTitleFamily,
} from '@/features/matching/hooks/useMatching'
import type { TitleFamilyItem, TitleFamilyListParams } from '@/types/matching'

const PAGE_SIZE = 50
const ALL = 'all'
const AMBIGUOUS = 'ambiguous'

function FamilyCell({ item, families }: { item: TitleFamilyItem; families: { key: string; label: string }[] }) {
  const update = useUpdateTitleFamily()
  return (
    <Select
      value={item.role_family ?? AMBIGUOUS}
      disabled={update.isPending}
      onValueChange={(next) =>
        update.mutate({ title: item.title_key, roleFamily: next === AMBIGUOUS ? null : next })
      }
    >
      <SelectTrigger className="h-8 w-56 text-sm">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={AMBIGUOUS}>Ambiguous (read the description)</SelectItem>
        {families.map((family) => (
          <SelectItem key={family.key} value={family.key}>
            {family.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/**
 * Title → role family cache. Pinning a title here overrides the classifier for every
 * job with that normalized title; existing match results are not re-judged.
 */
export default function TitleFamiliesPage() {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [familyFilter, setFamilyFilter] = useState(ALL)
  const [statusFilter, setStatusFilter] = useState(ALL)
  const [page, setPage] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(search.trim())
      setPage(0)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [search])

  const params: TitleFamilyListParams = {
    q: debounced || undefined,
    role_family: familyFilter === ALL ? undefined : familyFilter,
    status: statusFilter === ALL ? undefined : (statusFilter as TitleFamilyListParams['status']),
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }
  const { data, isLoading, isError } = useTitleFamilies(params)
  const { data: families = [] } = useRoleFamilies()
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Title role families</h1>
        <p className="text-sm text-slate-500">
          Fix how job titles are classified. Changes apply to jobs with the same normalized title; jobs set to
          ambiguous get their description read on the next matching run. Existing match results are kept.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search titles"
          className="max-w-xs"
        />
        <Select
          value={familyFilter}
          onValueChange={(value) => {
            setFamilyFilter(value)
            setPage(0)
          }}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Family" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All families</SelectItem>
            {families.map((family) => (
              <SelectItem key={family.key} value={family.key}>
                {family.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={statusFilter}
          onValueChange={(value) => {
            setStatusFilter(value)
            setPage(0)
          }}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            <SelectItem value="classified">Classified</SelectItem>
            <SelectItem value="ambiguous">Ambiguous</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Role family</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3 text-right">Jobs</th>
              <th className="px-4 py-3">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="p-4">
                  <Skeleton className="h-6 w-full" />
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={5} className="p-4 text-red-600">
                  Failed to load titles.
                </td>
              </tr>
            ) : data?.items.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-4 text-slate-500">
                  No titles found.
                </td>
              </tr>
            ) : (
              data?.items.map((item) => (
                <tr key={item.title_key}>
                  <td className="px-4 py-2">
                    <div className="font-medium text-slate-900">{item.example_title}</div>
                    <div className="text-xs text-slate-500">{item.title_key}</div>
                  </td>
                  <td className="px-4 py-2">
                    <FamilyCell item={item} families={families} />
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant="outline" className={item.source === 'admin' ? 'border-violet-300 text-violet-700' : ''}>
                      {item.source}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">{item.job_count}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">
                    {formatDistanceToNow(new Date(item.updated_at), { addSuffix: true })}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>{data?.total ?? 0} titles</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span>
            {page + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
