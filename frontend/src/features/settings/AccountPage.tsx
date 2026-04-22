import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Loader2 } from 'lucide-react'

import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import { ApiError } from '@/types/api'
import { Badge } from '@/components/ui/badge'
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

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/\d/, 'Password must contain at least one number')
      .regex(/[a-zA-Z]/, 'Password must contain at least one letter'),
    confirmPassword: z.string(),
  })
  .refine((values) => values.new_password === values.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  })

type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>

function formatDateTime(value?: string | null) {
  if (!value) return 'Never'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toLocaleString()
}

export default function AccountPage() {
  const { user, setUser } = useAuthStore()
  const { toast } = useToast()

  const [isEditingEmail, setIsEditingEmail] = useState(false)
  const [isEditingPassword, setIsEditingPassword] = useState(false)
  const [isResending, setIsResending] = useState(false)
  const [emailSubmitting, setEmailSubmitting] = useState(false)
  const [passwordSubmitting, setPasswordSubmitting] = useState(false)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)

  const emailForm = useForm<ChangeEmailFormValues>({
    resolver: zodResolver(changeEmailSchema),
    defaultValues: { new_email: '', current_password: '' },
  })

  const passwordForm = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: '', new_password: '', confirmPassword: '' },
  })

  const emailVerified = Boolean(user?.email_verified_at)
  const passwordLastChanged = useMemo(
    () => formatDateTime(user?.password_changed_at),
    [user?.password_changed_at],
  )

  const handleResend = async () => {
    setIsResending(true)
    try {
      const result = await authApi.resendVerificationEmail()
      toast({ title: 'Verification email', description: result.message })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Unable to resend verification email.'
      toast({ title: 'Request failed', description: message, variant: 'destructive' })
    } finally {
      setIsResending(false)
    }
  }

  const handleCancelEmail = () => {
    emailForm.reset()
    setEmailError(null)
    setIsEditingEmail(false)
  }

  const handleCancelPassword = () => {
    passwordForm.reset()
    setPasswordError(null)
    setIsEditingPassword(false)
  }

  const onSubmitEmail = async (values: ChangeEmailFormValues) => {
    setEmailSubmitting(true)
    setEmailError(null)
    try {
      const result = await authApi.requestEmailChange(values)
      const currentUser = await authApi.getCurrentUser()
      setUser(currentUser)
      emailForm.reset()
      setIsEditingEmail(false)
      toast({ title: 'Confirmation sent', description: result.message })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Unable to request email change.'
      setEmailError(message)
    } finally {
      setEmailSubmitting(false)
    }
  }

  const onSubmitPassword = async (values: ChangePasswordFormValues) => {
    setPasswordSubmitting(true)
    setPasswordError(null)
    try {
      const result = await authApi.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      })
      const currentUser = await authApi.getCurrentUser()
      setUser(currentUser)
      passwordForm.reset()
      setIsEditingPassword(false)
      toast({ title: 'Password changed', description: result.message })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Unable to change password.'
      setPasswordError(message)
    } finally {
      setPasswordSubmitting(false)
    }
  }

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Email</CardTitle>
          <CardDescription>Your sign-in email. Changing it requires confirmation at the new address.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="font-medium text-slate-900">{user?.email ?? 'Unknown'}</div>
              <div className="mt-1 flex items-center gap-2 text-sm">
                {emailVerified ? (
                  <Badge className="bg-emerald-600 hover:bg-emerald-600">Verified</Badge>
                ) : (
                  <Badge variant="outline" className="border-amber-500 text-amber-700">Not verified</Badge>
                )}
                {emailVerified ? (
                  <span className="text-slate-500">
                    on {formatDateTime(user?.email_verified_at)}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleResend}
                disabled={isResending || emailVerified}
              >
                {isResending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {emailVerified ? 'Already verified' : 'Resend verification'}
              </Button>
            </div>
          </div>

          {isEditingEmail ? (
            <Form {...emailForm}>
              <form onSubmit={emailForm.handleSubmit(onSubmitEmail)} className="space-y-4 rounded-lg border border-slate-200 p-4">
                <FormField
                  control={emailForm.control}
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
                  control={emailForm.control}
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
                {emailError ? <p className="text-sm text-red-600">{emailError}</p> : null}
                <div className="flex gap-2">
                  <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700" disabled={emailSubmitting}>
                    {emailSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {emailSubmitting ? 'Sending...' : 'Request change'}
                  </Button>
                  <Button type="button" variant="ghost" onClick={handleCancelEmail}>
                    Cancel
                  </Button>
                </div>
              </form>
            </Form>
          ) : (
            <Button variant="outline" onClick={() => setIsEditingEmail(true)}>
              Change email
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>Use a strong password you don't reuse elsewhere.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
            <div className="text-slate-500">Last changed</div>
            <div className="mt-1 font-medium text-slate-900">{passwordLastChanged}</div>
          </div>

          {isEditingPassword ? (
            <Form {...passwordForm}>
              <form onSubmit={passwordForm.handleSubmit(onSubmitPassword)} className="space-y-4 rounded-lg border border-slate-200 p-4">
                <FormField
                  control={passwordForm.control}
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
                <FormField
                  control={passwordForm.control}
                  name="new_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>New password</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder="********" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={passwordForm.control}
                  name="confirmPassword"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Confirm new password</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder="********" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {passwordError ? <p className="text-sm text-red-600">{passwordError}</p> : null}
                <div className="flex gap-2">
                  <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700" disabled={passwordSubmitting}>
                    {passwordSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {passwordSubmitting ? 'Updating...' : 'Update password'}
                  </Button>
                  <Button type="button" variant="ghost" onClick={handleCancelPassword}>
                    Cancel
                  </Button>
                </div>
              </form>
            </Form>
          ) : (
            <Button variant="outline" onClick={() => setIsEditingPassword(true)}>
              Change password
            </Button>
          )}
        </CardContent>
      </Card>

      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-700">Danger zone</CardTitle>
          <CardDescription>Irreversible actions. Proceed with caution.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm">
              <div className="font-medium text-slate-900">Delete account</div>
              <div className="text-slate-600">Permanently remove your account and all associated data.</div>
            </div>
            <Button variant="destructive" disabled title="Coming soon">
              Delete account
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
