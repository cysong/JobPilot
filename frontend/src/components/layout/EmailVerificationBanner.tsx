import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { authApi } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/ui/use-toast'
import { useAuthStore } from '@/store/authStore'
import { ApiError } from '@/types/api'

export function EmailVerificationBanner() {
  const { user } = useAuthStore()
  const { toast } = useToast()
  const [isSending, setIsSending] = useState(false)
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    if (!user || user.email_verified_at) {
      setIsVisible(false)
      return
    }

    setIsVisible(true)
    const timer = window.setTimeout(() => {
      setIsVisible(false)
    }, 10000)

    return () => {
      window.clearTimeout(timer)
    }
  }, [user?.id, user?.email_verified_at])

  if (!user || user.email_verified_at || !isVisible) {
    return null
  }

  const handleResend = async () => {
    setIsSending(true)
    try {
      const result = await authApi.resendVerificationEmail()
      toast({
        title: 'Verification email',
        description: result.message,
      })
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : 'Unable to resend verification email.'
      toast({
        title: 'Request failed',
        description: message,
        variant: 'destructive',
      })
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="border-b border-amber-200 bg-amber-50">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-6 py-3 text-sm text-amber-950 md:flex-row md:items-center md:justify-between">
        <div>
          Your email is not verified yet. Verify it to keep your account security settings up to date.
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" className="border-amber-300 bg-white" onClick={handleResend} disabled={isSending}>
            {isSending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Resend email
          </Button>
          <Button asChild size="sm" className="bg-amber-600 hover:bg-amber-700">
            <Link to="/settings/account">Open account settings</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
