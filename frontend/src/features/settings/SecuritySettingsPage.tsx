import { useState } from 'react'
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
  if (!value) {
    return 'Never'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return 'Unknown'
  }
  return date.toLocaleString()
}

export default function SecuritySettingsPage() {
  const { user, setUser } = useAuthStore()
  const { toast } = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const form = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirmPassword: '',
    },
  })

  const onSubmit = async (values: ChangePasswordFormValues) => {
    setIsSubmitting(true)
    setSubmitError(null)

    try {
      const result = await authApi.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      })
      const currentUser = await authApi.getCurrentUser()
      setUser(currentUser)
      form.reset()
      toast({
        title: 'Password changed',
        description: result.message,
      })
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : 'Unable to change password.'
      setSubmitError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="container mx-auto max-w-4xl p-6 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">Security</h1>
        <p className="mt-2 text-slate-600">Manage your password and review your account security status.</p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Password</CardTitle>
            <CardDescription>Update your password. You must confirm your current password first.</CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
                <FormField
                  control={form.control}
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
                  control={form.control}
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

                {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}

                <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700" disabled={isSubmitting}>
                  {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  {isSubmitting ? 'Updating...' : 'Change password'}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Security summary</CardTitle>
            <CardDescription>Current account-level security information from your profile.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm text-slate-700">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <span className="text-slate-500">Email verification</span>
              <span>{user?.email_verified_at ? 'Verified' : 'Not verified'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Password last changed</span>
              <span>{formatDateTime(user?.password_changed_at)}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
