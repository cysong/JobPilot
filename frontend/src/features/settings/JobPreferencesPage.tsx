import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Loader2 } from 'lucide-react'

import { usersApi } from '@/api/users'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import type { UserPreferences } from '@/types/auth'
import { ApiError } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/ui/use-toast'

const NZ_JOB_LOCATIONS = [
  'Auckland',
  'Wellington',
  'Christchurch',
  'Hamilton',
  'Tauranga',
  'Dunedin',
  'Palmerston North',
  'Queenstown',
  'Napier-Hastings',
  'Nelson',
] as const

type SalaryMode = 'unset' | 'exact' | 'range'

interface PreferencesFormValues {
  default_tailoring_level: 'light' | 'moderate' | 'deep'
  job_locations: string[]
  salary_mode: SalaryMode
  salary_exact: string
  salary_min: string
  salary_max: string
}

export default function JobPreferencesPage() {
  const { user, setUser } = useAuthStore()
  const { toast } = useToast()
  const [isSaving, setIsSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const form = useForm<PreferencesFormValues>({
    defaultValues: {
      default_tailoring_level: 'light',
      job_locations: [],
      salary_mode: 'unset',
      salary_exact: '',
      salary_min: '',
      salary_max: '',
    },
  })

  useEffect(() => {
    const preferences = user?.preferences
    const salary = preferences?.salary_expectation

    form.reset({
      default_tailoring_level: preferences?.default_tailoring_level ?? 'light',
      job_locations: preferences?.job_locations ?? [],
      salary_mode: salary?.mode ?? 'unset',
      salary_exact: salary?.mode === 'exact' && salary.value != null ? String(salary.value) : '',
      salary_min: salary?.mode === 'range' && salary.min != null ? String(salary.min) : '',
      salary_max: salary?.mode === 'range' && salary.max != null ? String(salary.max) : '',
    })
  }, [form, user])

  const salaryMode = form.watch('salary_mode')
  const selectedLocations = form.watch('job_locations')

  const onSubmit = async (values: PreferencesFormValues) => {
    setIsSaving(true)
    setLoadError(null)

    try {
      let salaryExpectation: UserPreferences['salary_expectation'] = null

      if (values.salary_mode === 'exact') {
        const value = Number(values.salary_exact)
        if (!Number.isFinite(value) || value <= 0) {
          throw new Error('Please enter a valid expected yearly salary.')
        }
        salaryExpectation = {
          mode: 'exact',
          currency: 'NZD',
          period: 'yearly',
          value,
          min: null,
          max: null,
        }
      }

      if (values.salary_mode === 'range') {
        const min = Number(values.salary_min)
        const max = Number(values.salary_max)
        if (!Number.isFinite(min) || !Number.isFinite(max) || min <= 0 || max <= 0 || max < min) {
          throw new Error('Please enter a valid yearly salary range.')
        }
        salaryExpectation = {
          mode: 'range',
          currency: 'NZD',
          period: 'yearly',
          min,
          max,
          value: null,
        }
      }

      await usersApi.updateProfilePreferences({
        default_tailoring_level: values.default_tailoring_level,
        job_locations: values.job_locations,
        salary_expectation: salaryExpectation,
      })

      const currentUser = await authApi.getCurrentUser()
      setUser(currentUser)

      toast({
        title: 'Preferences saved',
        description: 'Your job preferences have been updated.',
      })
    } catch (err: unknown) {
      const message =
        err instanceof ApiError || err instanceof Error
          ? err.message
          : 'Unable to save your preferences.'
      setLoadError(message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Job Preferences</CardTitle>
        <CardDescription>These defaults are used when you start a new application.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
            <FormField
              control={form.control}
              name="default_tailoring_level"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Default tailoring level</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="max-w-sm">
                        <SelectValue placeholder="Select default tailoring level" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="light">Light tailoring</SelectItem>
                      <SelectItem value="moderate">Moderate tailoring</SelectItem>
                      <SelectItem value="deep">Deep tailoring</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="job_locations"
              render={() => (
                <FormItem>
                  <FormLabel>Preferred NZ job locations</FormLabel>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {NZ_JOB_LOCATIONS.map((location) => (
                      <label
                        key={location}
                        className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      >
                        <Checkbox
                          checked={selectedLocations.includes(location)}
                          onCheckedChange={(checked) => {
                            const next = checked
                              ? [...selectedLocations, location]
                              : selectedLocations.filter((item) => item !== location)
                            form.setValue('job_locations', next, { shouldDirty: true })
                          }}
                        />
                        <span>{location}</span>
                      </label>
                    ))}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="salary_mode"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Expected yearly salary</FormLabel>
                  <Select value={field.value} onValueChange={(value: SalaryMode) => field.onChange(value)}>
                    <FormControl>
                      <SelectTrigger className="max-w-sm">
                        <SelectValue placeholder="Select salary input mode" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="unset">Not set</SelectItem>
                      <SelectItem value="exact">Exact yearly salary</SelectItem>
                      <SelectItem value="range">Yearly salary range</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {salaryMode === 'exact' ? (
              <FormField
                control={form.control}
                name="salary_exact"
                render={({ field }) => (
                  <FormItem className="max-w-sm">
                    <FormLabel>Expected yearly salary (NZD)</FormLabel>
                    <FormControl>
                      <Input inputMode="numeric" placeholder="120000" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            {salaryMode === 'range' ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="salary_min"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Minimum yearly salary (NZD)</FormLabel>
                      <FormControl>
                        <Input inputMode="numeric" placeholder="110000" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="salary_max"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Maximum yearly salary (NZD)</FormLabel>
                      <FormControl>
                        <Input inputMode="numeric" placeholder="150000" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            ) : null}

            {loadError ? <p className="text-sm text-red-600">{loadError}</p> : null}

            <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700" disabled={isSaving}>
              {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {isSaving ? 'Saving...' : 'Save preferences'}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
