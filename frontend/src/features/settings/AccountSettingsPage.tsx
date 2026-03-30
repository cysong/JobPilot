import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Loader2 } from 'lucide-react'

import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import { ApiError } from '@/types/api'
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

const changeEmailSchema = z.object({
  new_email: z.string().email('Please enter a valid email address'),
  current_password: z.string().min(1, 'Current password is required'),
})

type ChangeEmailFormValues = z.infer<typeof changeEmailSchema>

function formatVerifiedStatus(emailVerifiedAt?: string | null) {
  if (!emailVerifiedAt) {
    return 'Not verified'
  }
  const parsed = new Date(emailVerifiedAt)
  if (Number.isNaN(parsed.getTime())) {
    return 'Verified'
  }
  return `Verified on ${parsed.toLocaleString()}`
}

export default function AccountSettingsPage() {
  const { user, setUser } = useAuthStore()
  const { toast } = useToast()
  const [isResending, setIsResending] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const form = useForm<ChangeEmailFormValues>({
    resolver: zodResolver(changeEmailSchema),
    defaultValues: {
      new_email: '',
      current_password: '',
    },
  })

  const emailStatus = useMemo(() => formatVerifiedStatus(user?.email_verified_at), [user?.email_verified_at])

  const handleResend = async () => {
    setIsResending(true)
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
      setIsResending(false)
    }
  }

  const onSubmit = async (values: ChangeEmailFormValues) => {
    setIsSubmitting(true)
    setSubmitError(null)

    try {
      const result = await authApi.requestEmailChange(values)
      const currentUser = await authApi.getCurrentUser()
      setUser(currentUser)
      form.reset()
      toast({
        title: 'Confirmation sent',
        description: result.message,
      })
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : 'Unable to request email change.'
      setSubmitError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="container mx-auto max-w-4xl p-6 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">Account</h1>
        <p className="mt-2 text-slate-600">Manage your email address and verification status.</p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Current email</CardTitle>
            <CardDescription>Verification is required for a fully trusted account.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="text-sm text-slate-500">Email</div>
              <div className="mt-1 font-medium text-slate-900">{user?.email ?? 'Unknown'}</div>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm text-slate-500">Verification status</div>
                <div className="mt-1 text-sm font-medium text-slate-900">{emailStatus}</div>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={handleResend}
                disabled={isResending || Boolean(user?.email_verified_at)}
              >
                {isResending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {user?.email_verified_at ? 'Already verified' : 'Resend verification email'}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Change email</CardTitle>
            <CardDescription>
              Enter your new email address and current password. A confirmation link will be sent to the new email.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="new_email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>New email</FormLabel>
                      <FormControl>
                        <Input type="email" placeholder="new@example.com" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="current_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Current password</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder="********" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}

                <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700" disabled={isSubmitting}>
                  {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  {isSubmitting ? 'Sending...' : 'Request email change'}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
