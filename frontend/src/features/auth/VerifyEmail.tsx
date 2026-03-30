import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'

import AuthPageFrame from '@/features/auth/AuthPageFrame'
import { authApi } from '@/api/auth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/ui/use-toast'
import { ApiError } from '@/types/api'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const { toast } = useToast()
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  const token = useMemo(() => searchParams.get('token')?.trim() ?? '', [searchParams])

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      if (!token) {
        setStatus('error')
        setError('Verification token is missing.')
        return
      }

      setStatus('loading')
      setError(null)

      try {
        const result = await authApi.verifyEmail({ token })
        if (cancelled) {
          return
        }
        setStatus('success')
        toast({
          title: 'Email verified',
          description: result.message,
        })
      } catch (err: unknown) {
        if (cancelled) {
          return
        }
        const message = err instanceof ApiError ? err.message : 'Unable to verify email.'
        setStatus('error')
        setError(message)
      }
    }

    void run()

    return () => {
      cancelled = true
    }
  }, [token, toast])

  return (
    <AuthPageFrame
      title="Verify email"
      description="We are confirming your email address."
      footer={
        <div className="text-sm text-slate-600">
          Continue to{' '}
          <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500 hover:underline">
            Sign in
          </Link>
        </div>
      }
    >
      {status === 'loading' ? (
        <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
          Verifying your email...
        </div>
      ) : null}

      {status === 'success' ? (
        <Alert>
          <CheckCircle2 className="h-4 w-4" />
          <AlertTitle>Email verified</AlertTitle>
          <AlertDescription>Your email has been verified successfully.</AlertDescription>
        </Alert>
      ) : null}

      {status === 'error' ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Verification failed</AlertTitle>
          <AlertDescription>{error ?? 'Unable to verify email.'}</AlertDescription>
        </Alert>
      ) : null}

      {status === 'error' ? (
        <Button asChild variant="outline" className="w-full">
          <Link to="/login">Back to sign in</Link>
        </Button>
      ) : null}
    </AuthPageFrame>
  )
}
