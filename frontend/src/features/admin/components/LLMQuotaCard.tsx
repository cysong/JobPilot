import { formatDistanceToNow } from 'date-fns'
import { Loader2, PauseCircle, PlayCircle } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { adminApi } from '@/api/admin'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'

const usd = (value: number | null | undefined) => (value == null ? '—' : `$${value.toFixed(2)}`)

/** LLM quota pause status: AI work stops while the OpenRouter key is out of credit. */
export function LLMQuotaCard() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'llm-quota'],
    queryFn: adminApi.getLLMQuota,
    refetchInterval: 60_000,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['admin', 'llm-quota'] })
  const resume = useMutation({
    mutationFn: adminApi.resumeLLMWork,
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

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">LLM quota</CardTitle>
        {data ? (
          data.paused ? (
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
              <span>Remaining: {usd(data.key_remaining)}</span>
              <span>Used: {usd(data.key_usage)}</span>
              <span>Key limit: {data.key_limit == null ? 'none' : usd(data.key_limit)}</span>
              <span>Pause below: {usd(data.threshold_usd)}</span>
            </div>
            {data.paused ? (
              <p className="text-red-700">
                {data.reason}
                {data.since ? ` · since ${formatDistanceToNow(new Date(data.since * 1000), { addSuffix: true })}` : ''}
              </p>
            ) : null}
            <div className="flex gap-2">
              {data.paused ? (
                <Button size="sm" onClick={() => resume.mutate()} disabled={resume.isPending}>
                  <PlayCircle className="mr-2 h-4 w-4" />
                  Resume
                </Button>
              ) : (
                <Button size="sm" variant="outline" onClick={() => pause.mutate()} disabled={pause.isPending}>
                  <PauseCircle className="mr-2 h-4 w-4" />
                  Pause
                </Button>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
