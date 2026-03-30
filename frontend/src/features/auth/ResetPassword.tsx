import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { AlertCircle, Loader2 } from 'lucide-react'

import AuthPageFrame from '@/features/auth/AuthPageFrame'
import { authApi } from '@/api/auth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
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
import { ApiError } from '@/types/api'

const resetPasswordSchema = z
  .object({
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

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>

export default function ResetPassword() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { toast } = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [completed, setCompleted] = useState(false)

  const token = useMemo(() => searchParams.get('token')?.trim() ?? '', [searchParams])

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      new_password: '',
      confirmPassword: '',
    },
  })

  const onSubmit = async (values: ResetPasswordFormValues) => {
    if (!token) {
      setError('Reset token is missing.')
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      const result = await authApi.resetPassword({
        token,
        new_password: values.new_password,
      })
      setCompleted(true)
      toast({
        title: 'Password updated',
        description: result.message,
      })
      setTimeout(() => navigate('/login'), 1200)
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : 'Unable to reset password.'
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthPageFrame
      title="Reset password"
      description="Choose a new password for your account."
      footer={
        <div className="text-sm text-slate-600">
          Back to{' '}
          <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500 hover:underline">
            Sign in
          </Link>
        </div>
      }
    >
      {!token ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Invalid link</AlertTitle>
          <AlertDescription>The reset token is missing or malformed.</AlertDescription>
        </Alert>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {completed ? (
        <Alert>
          <AlertTitle>Password updated</AlertTitle>
          <AlertDescription>Your password has been reset. Redirecting to sign in...</AlertDescription>
        </Alert>
      ) : null}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
          <Button
            type="submit"
            className="w-full bg-indigo-600 hover:bg-indigo-700"
            disabled={isSubmitting || !token}
          >
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {isSubmitting ? 'Resetting...' : 'Reset password'}
          </Button>
        </form>
      </Form>
    </AuthPageFrame>
  )
}
