import { formatDistanceToNow } from 'date-fns'
import { Loader2, PauseCircle, PlayCircle } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { adminApi } from '@/api/admin'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'

const usd = (value: number | null | undefined) => (value == null ? '—' : `$${value.toFixed(2)}`)

const KIND_LABEL: Record<string, string> = {
  quota: 'Out of credit',
  auth: 'API key rejected',
  model: 'Model unavailable',
  outage: 'Provider down (breaker)',
  manual: 'Paused by admin',
}

/** LLM pauses: AI work is parked while a cause that retrying cannot fix is active. */
export function LLMAvailabilityCard() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'llm-availability'],
    queryFn: adminApi.getLLMAvailability,
    refetchInterval: 60_000,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['admin', 'llm-availability'] })
  const resume = useMutation({
    mutationFn: (scope?: string) => adminApi.resumeLLMWork(scope),
    onSuccess: (result) => {
      refresh()
      toast({ title: 'LLM work resumed', description: `${result.resubmitted} parked workflows resubmitted.` })
    },
    onError: () => toast({ title: 'Error', description: 'Failed to resume', variant: 'destructive' }),
  })
  const pause = useMutation({
    mutationFn: adminApi.pauseLLMWork,
    onSuccess: refresh,
    onError: () => toast({ title: 'Error', description: 'Failed to pause', variant: 'destructive' }),
  })
  const paused = (data?.pauses.length ?? 0) > 0

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">LLM availability</CardTitle>
        {data ? (
          paused ? (
            <Badge className="bg-red-600 text-white hover:bg-red-600">Paused</Badge>
          ) : (
            <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">Running</Badge>
          )
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {isLoading || !data ? (
          <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
        ) : (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-slate-600">
              <span>Key: {data.key_ok === false ? 'rejected' : data.key_ok ? 'ok' : 'unknown'}</span>
              <span>Remaining: {usd(data.key_remaining)}</span>
              <span>Used: {usd(data.key_usage)}</span>
              <span>Key limit: {data.key_limit == null ? 'none' : usd(data.key_limit)}</span>
              <span>Pause below: {usd(data.threshold_usd)}</span>
            </div>
            {data.pauses.map((item) => (
              <div
                key={item.scope}
                className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3"
              >
                <div className="min-w-0 space-y-1">
                  <p className="font-medium text-red-800">
                    {KIND_LABEL[item.kind] ?? item.kind} · {item.scope}
                  </p>
                  <p className="break-words text-xs text-red-700">{item.reason}</p>
                  <p className="text-xs text-red-600">
                    {item.since ? `since ${formatDistanceToNow(new Date(item.since * 1000), { addSuffix: true })}` : ''}
                    {item.expires_in ? ` · retries in ${Math.ceil(item.expires_in / 60)} min` : ''}
                  </p>
                </div>
                <Button size="sm" onClick={() => resume.mutate(item.scope)} disabled={resume.isPending}>
                  <PlayCircle className="mr-2 h-4 w-4" />
                  Resume
                </Button>
              </div>
            ))}
            {!data.pauses.some((item) => item.scope === 'global') ? (
              <Button size="sm" variant="outline" onClick={() => pause.mutate()} disabled={pause.isPending}>
                <PauseCircle className="mr-2 h-4 w-4" />
                Pause all
              </Button>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}
