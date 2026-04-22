import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Loader2, Shuffle } from 'lucide-react'

import { usersApi } from '@/api/users'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import { ApiError } from '@/types/api'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
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
import { getAvatarUrl, randomAvatarSeed } from '@/lib/avatar'
import { Role } from '@/types/auth'

const profileSchema = z.object({
  full_name: z.string().min(1, 'Name is required').max(255, 'Name is too long'),
})

type ProfileFormValues = z.infer<typeof profileSchema>

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString()
}

export default function ProfilePage() {
  const { user, setUser } = useAuthStore()
  const { toast } = useToast()
  const [isSaving, setIsSaving] = useState(false)
  const [isAvatarSaving, setIsAvatarSaving] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user?.full_name ?? '',
    },
  })

  useEffect(() => {
    form.reset({ full_name: user?.full_name ?? '' })
  }, [form, user?.full_name])

  const avatarUrl = getAvatarUrl(user)
  const initials = user?.full_name
    ? user.full_name.substring(0, 2).toUpperCase()
    : user?.email?.substring(0, 2).toUpperCase() ?? 'JP'

  const handleRandomizeAvatar = async () => {
    setIsAvatarSaving(true)
    try {
      const updated = await usersApi.updateProfile({ avatar_seed: randomAvatarSeed() })
      setUser(updated)
      toast({ title: 'Avatar updated', description: 'A fresh avatar has been generated.' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Unable to update avatar.'
      toast({ title: 'Request failed', description: message, variant: 'destructive' })
    } finally {
      setIsAvatarSaving(false)
    }
  }

  const onSubmit = async (values: ProfileFormValues) => {
    setIsSaving(true)
    setSubmitError(null)
    try {
      await usersApi.updateProfile({ full_name: values.full_name.trim() })
      const currentUser = await authApi.getCurrentUser()
      setUser(currentUser)
      toast({ title: 'Profile saved', description: 'Your profile has been updated.' })
    } catch (err) {
      const message = err instanceof ApiError || err instanceof Error ? err.message : 'Unable to save profile.'
      setSubmitError(message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Avatar</CardTitle>
          <CardDescription>A generated icon based on a private seed. You can regenerate anytime.</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-4">
          <Avatar className="h-20 w-20">
            <AvatarImage src={avatarUrl} alt={user?.email || 'avatar'} />
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <Button variant="outline" onClick={handleRandomizeAvatar} disabled={isAvatarSaving}>
            {isAvatarSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Shuffle className="mr-2 h-4 w-4" />
            )}
            Randomize
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>Your display name and account details.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="full_name"
                render={({ field }) => (
                  <FormItem className="max-w-sm">
                    <FormLabel>Full name</FormLabel>
                    <FormControl>
                      <Input placeholder="Your name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <div className="text-slate-500">Email</div>
                  <div className="mt-1 font-medium text-slate-900">{user?.email ?? '—'}</div>
                </div>
                <div>
                  <div className="text-slate-500">Account created</div>
                  <div className="mt-1 font-medium text-slate-900">{formatDate(user?.created_at)}</div>
                </div>
                {user?.role === Role.ADMIN ? (
                  <div>
                    <div className="text-slate-500">Role</div>
                    <div className="mt-1">
                      <Badge className="bg-indigo-600 hover:bg-indigo-600">Administrator</Badge>
                    </div>
                  </div>
                ) : null}
              </div>

              {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}

              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700" disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {isSaving ? 'Saving...' : 'Save changes'}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
