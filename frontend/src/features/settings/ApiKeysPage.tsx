import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { formatDistanceToNow } from 'date-fns'
import { AlertTriangle, Check, Copy, Loader2 } from 'lucide-react'

import { apiKeysApi } from '@/api/apiKeys'
import { ApiError } from '@/types/api'
import type { ApiKey, ApiKeyCreated } from '@/types/apiKeys'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { useToast } from '@/components/ui/use-toast'

const createSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Name is required')
    .max(100, 'Name must be at most 100 characters'),
})
type CreateFormValues = z.infer<typeof createSchema>

function relativeOrNever(value: string | null) {
  if (!value) return 'Never'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return `${formatDistanceToNow(date, { addSuffix: true })}`
}

function relative(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return formatDistanceToNow(date, { addSuffix: true })
}

export default function ApiKeysPage() {
  const { toast } = useToast()

  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [isCreating, setIsCreating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [revealed, setRevealed] = useState<ApiKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)

  const [revokeTargetId, setRevokeTargetId] = useState<string | null>(null)
  const [revoking, setRevoking] = useState(false)

  const createForm = useForm<CreateFormValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '' },
  })

  const fetchKeys = async () => {
    setLoadError(null)
    try {
      const data = await apiKeysApi.list()
      setKeys(data)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load API keys.'
      setLoadError(message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchKeys()
  }, [])

  const revealedListed = useMemo(
    () => keys.find((k) => revealed && k.id === revealed.id) ?? null,
    [keys, revealed],
  )

  const handleStartCreate = () => {
    setIsCreating(true)
    setCreateError(null)
    createForm.reset({ name: '' })
  }

  const handleCancelCreate = () => {
    setIsCreating(false)
    setCreateError(null)
    createForm.reset({ name: '' })
  }

  const onSubmitCreate = async (values: CreateFormValues) => {
    setSubmitting(true)
    setCreateError(null)
    try {
      const created = await apiKeysApi.create({ name: values.name })
      setRevealed(created)
      setCopied(false)
      setIsCreating(false)
      createForm.reset({ name: '' })
      await fetchKeys()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to create API key.'
      setCreateError(message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleCopy = async () => {
    if (!revealed) return
    try {
      await navigator.clipboard.writeText(revealed.plaintext)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast({
        title: 'Copy failed',
        description: 'Select the key text manually and copy it.',
        variant: 'destructive',
      })
    }
  }

  const handleRequestRevoke = (id: string) => {
    setRevokeTargetId(id)
  }

  const handleCancelRevoke = () => {
    setRevokeTargetId(null)
  }

  const handleConfirmRevoke = async (id: string) => {
    setRevoking(true)
    try {
      await apiKeysApi.revoke(id)
      setKeys((prev) => prev.filter((k) => k.id !== id))
      if (revealed?.id === id) setRevealed(null)
      toast({ title: 'API key revoked', description: 'Calls using this key will now fail.' })
      setRevokeTargetId(null)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to revoke API key.'
      toast({ title: 'Revoke failed', description: message, variant: 'destructive' })
      // Re-sync in case the key was already revoked server-side.
      await fetchKeys()
    } finally {
      setRevoking(false)
    }
  }

  const renderRevokeBlock = (key: ApiKey) => (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
      <div className="font-medium text-slate-900">{key.name}</div>
      <p className="mt-1 text-sm text-red-700">
        Revoke this key? Calls using it will fail immediately and this cannot be undone.
      </p>
      <div className="mt-3 flex gap-2">
        <Button
          type="button"
          variant="destructive"
          size="sm"
          onClick={() => handleConfirmRevoke(key.id)}
          disabled={revoking}
        >
          {revoking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Revoke
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={handleCancelRevoke} disabled={revoking}>
          Cancel
        </Button>
      </div>
    </div>
  )

  const renderRevealedItem = (created: ApiKeyCreated) => (
    <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3">
      <div className="flex items-center gap-2 text-amber-800">
        <AlertTriangle className="h-4 w-4" />
        <span className="text-sm font-medium">
          Save this key now — it won't be shown again.
        </span>
      </div>
      <div className="mt-3 font-medium text-slate-900">{created.name}</div>
      <div className="mt-2 flex items-stretch gap-2">
        <code className="flex-1 break-all rounded-md border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-900">
          {created.plaintext}
        </code>
        <Button
          type="button"
          variant="outline"
          onClick={handleCopy}
          className="shrink-0"
          aria-label="Copy API key"
        >
          {copied ? (
            <>
              <Check className="mr-2 h-4 w-4" />
              Copied
            </>
          ) : (
            <>
              <Copy className="mr-2 h-4 w-4" />
              Copy
            </>
          )}
        </Button>
      </div>
      <div className="mt-3 text-xs text-slate-500">Created just now</div>
    </div>
  )

  const renderNormalItem = (key: ApiKey) => (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="font-medium text-slate-900">{key.name}</div>
        <div className="mt-1 font-mono text-sm text-slate-700">
          {key.prefix}
          <span className="text-slate-400">••••••••</span>
        </div>
        <div className="mt-1 text-xs text-slate-500">
          Created {relative(key.created_at)} · Last used {relativeOrNever(key.last_used_at)}
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => handleRequestRevoke(key.id)}
          className="border-red-200 text-red-700 hover:bg-red-50 hover:text-red-700"
        >
          Revoke
        </Button>
      </div>
    </div>
  )

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>
            Long-lived tokens for scripts and integrations. Treat them like passwords.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isCreating ? (
            <Form {...createForm}>
              <form
                onSubmit={createForm.handleSubmit(onSubmitCreate)}
                className="space-y-4 rounded-lg border border-slate-200 p-4"
              >
                <FormField
                  control={createForm.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., n8n-integration" autoFocus {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {createError ? <p className="text-sm text-red-600">{createError}</p> : null}
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-700"
                    disabled={submitting}
                  >
                    {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {submitting ? 'Generating...' : 'Generate'}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={handleCancelCreate}
                    disabled={submitting}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            </Form>
          ) : (
            <Button variant="outline" onClick={handleStartCreate}>
              + Generate new key
            </Button>
          )}

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading API keys...
            </div>
          ) : loadError ? (
            <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <span>{loadError}</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setLoading(true)
                  void fetchKeys()
                }}
              >
                Retry
              </Button>
            </div>
          ) : keys.length === 0 && !revealed ? (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
              No API keys yet. Generate one to start calling the JobPilot API from external tools.
            </div>
          ) : (
            <div className="space-y-3">
              {revealed && !revealedListed ? renderRevealedItem(revealed) : null}
              {keys.map((key) => {
                if (revealed && key.id === revealed.id) return (
                  <div key={key.id}>{renderRevealedItem(revealed)}</div>
                )
                if (revokeTargetId === key.id) return (
                  <div key={key.id}>{renderRevokeBlock(key)}</div>
                )
                return <div key={key.id}>{renderNormalItem(key)}</div>
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
