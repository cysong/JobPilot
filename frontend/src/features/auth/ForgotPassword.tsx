import { useState } from 'react'
import { Link } from 'react-router-dom'
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

const forgotPasswordSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
})

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>

export default function ForgotPassword() {
  const { toast } = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: '',
    },
  })

  const onSubmit = async (values: ForgotPasswordFormValues) => {
    setIsSubmitting(true)
    setError(null)
    try {
      const result = await authApi.forgotPassword(values)
      setSubmitted(true)
      toast({
        title: 'Check your inbox',
        description: result.message,
      })
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : 'Unable to send reset instructions.'
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthPageFrame
      title="Forgot password"
      description="Enter your email and we will send password reset instructions if the account exists."
      footer={
        <div className="text-sm text-slate-600">
          Remembered your password?{' '}
          <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500 hover:underline">
            Sign in
          </Link>
        </div>
      }
    >
      {error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {submitted ? (
        <Alert>
          <AlertTitle>Instructions sent</AlertTitle>
          <AlertDescription>
            If an account exists, we have sent password reset instructions.
          </AlertDescription>
        </Alert>
      ) : null}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input type="email" placeholder="name@example.com" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {isSubmitting ? 'Sending...' : 'Send reset instructions'}
          </Button>
        </form>
      </Form>
    </AuthPageFrame>
  )
}
