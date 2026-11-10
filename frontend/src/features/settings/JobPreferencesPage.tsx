import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Loader2 } from 'lucide-react'

import { usersApi } from '@/api/users'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import type { SecurityClearance, UserPreferences, WorkRights } from '@/types/auth'
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

const DEFAULT_COUNTRY = 'New Zealand'

const WORK_RIGHTS_OPTIONS: { value: WorkRights; label: string }[] = [
  { value: 'citizen', label: 'NZ citizen' },
  { value: 'permanent_resident', label: 'Permanent / resident visa' },
  { value: 'work_visa', label: 'Work visa (already allowed to work)' },
  { value: 'needs_sponsorship', label: 'Need visa sponsorship' },
]

const CLEARANCE_OPTIONS: { value: SecurityClearance; label: string }[] = [
  { value: 'holds', label: 'Currently hold a NZ security clearance' },
  { value: 'eligible', label: 'Eligible to obtain one' },
  { value: 'not_eligible', label: 'Not eligible' },
]

const COMMON_LANGUAGES = ['English', 'Chinese', 'Hindi', 'Japanese', 'Korean', 'Spanish', 'French', 'German'] as const

// Mirror the backend limits in ProfilePreferencesUpdate / SalaryExpectation.
const MAX_LANGUAGES = 10
const MAX_COUNTRY_LENGTH = 64

// Accepts "120000", "120,000" or "120 000"; returns null unless it is a
// positive whole number (the API stores salaries as integers).
const parseSalary = (raw: string): number | null => {
  const cleaned = raw.replace(/[,\s]/g, '')
  if (!/^\d+$/.test(cleaned)) return null
  const value = Number(cleaned)
  return Number.isSafeInteger(value) && value > 0 ? value : null
}

interface PreferencesFormValues {
  default_tailoring_level: 'light' | 'moderate' | 'deep'
  job_locations: string[]
  salary_mode: SalaryMode
  salary_exact: string
  salary_min: string
  salary_max: string
  work_rights: WorkRights | 'unset'
  security_clearance: SecurityClearance | 'unset'
  country: string
  languages: string[]
}

export default function JobPreferencesPage() {
  const { user, setUser } = useAuthStore()
  const { toast } = useToast()
  const [isSaving, setIsSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [workRightHint, setWorkRightHint] = useState<string | null>(null)
  const [otherLanguage, setOtherLanguage] = useState('')

  const form = useForm<PreferencesFormValues>({
    defaultValues: {
      default_tailoring_level: 'light',
      job_locations: [],
      salary_mode: 'unset',
      salary_exact: '',
      salary_min: '',
      salary_max: '',
      work_rights: 'unset',
      security_clearance: 'unset',
      country: DEFAULT_COUNTRY,
      languages: [],
    },
  })

  useEffect(() => {
    usersApi
      .getProfilePreferences()
      .then((preferences) => setWorkRightHint(preferences.work_right_hint ?? null))
      .catch(() => setWorkRightHint(null))
  }, [])

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
      work_rights: preferences?.work_rights ?? 'unset',
      security_clearance: preferences?.security_clearance ?? 'unset',
      country: preferences?.country ?? DEFAULT_COUNTRY,
      languages: preferences?.languages ?? [],
    })
  }, [form, user])

  const salaryMode = form.watch('salary_mode')
  const selectedLocations = form.watch('job_locations')
  const selectedLanguages = form.watch('languages')
  const languageChoices = [
    ...COMMON_LANGUAGES,
    ...selectedLanguages.filter((item) => !(COMMON_LANGUAGES as readonly string[]).includes(item)),
  ]

  const toggleLanguage = (language: string, checked: boolean) => {
    if (checked && selectedLanguages.length >= MAX_LANGUAGES) {
      setLoadError(`You can select up to ${MAX_LANGUAGES} languages.`)
      return
    }
    setLoadError(null)
    const next = checked
      ? [...selectedLanguages, language]
      : selectedLanguages.filter((item) => item !== language)
    form.setValue('languages', next, { shouldDirty: true })
  }

  const addOtherLanguage = () => {
    const language = otherLanguage.trim().replace(/\s+/g, ' ')
    if (language && !selectedLanguages.some((item) => item.toLowerCase() === language.toLowerCase())) {
      toggleLanguage(language, true)
    }
    setOtherLanguage('')
  }

  const onSubmit = async (values: PreferencesFormValues) => {
    setIsSaving(true)
    setLoadError(null)

    try {
      let salaryExpectation: UserPreferences['salary_expectation'] = null

      if (values.salary_mode === 'exact') {
        const value = parseSalary(values.salary_exact)
        if (value === null) {
          throw new Error('Please enter the expected yearly salary as a whole number, e.g. 120000.')
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
        const min = parseSalary(values.salary_min)
        const max = parseSalary(values.salary_max)
        if (min === null || max === null) {
          throw new Error('Please enter the salary range as whole numbers, e.g. 110000 and 150000.')
        }
        if (max < min) {
          throw new Error('The maximum salary must be greater than or equal to the minimum.')
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
        work_rights: values.work_rights === 'unset' ? null : values.work_rights,
        security_clearance: values.security_clearance === 'unset' ? null : values.security_clearance,
        country: values.country.trim() || null,
        languages: values.languages,
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

            <div className="space-y-6 border-t border-slate-200 pt-6">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Job matching conditions</h3>
                <p className="text-sm text-slate-500">
                  Jobs whose description explicitly requires something you don&apos;t meet are marked as
                  rejected. Leave a field unset to never reject on it.
                </p>
              </div>

              <FormField
                control={form.control}
                name="work_rights"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Work rights in New Zealand</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="max-w-sm">
                          <SelectValue placeholder="Select work rights" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="unset">Not set</SelectItem>
                        {WORK_RIGHTS_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {workRightHint ? (
                      <p className="text-xs text-slate-500">Your resume says: {workRightHint}</p>
                    ) : null}
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="security_clearance"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Security clearance</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="max-w-sm">
                          <SelectValue placeholder="Select security clearance" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="unset">Not set</SelectItem>
                        {CLEARANCE_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="country"
                render={({ field }) => (
                  <FormItem className="max-w-sm">
                    <FormLabel>Country you live in</FormLabel>
                    <FormControl>
                      <Input placeholder={DEFAULT_COUNTRY} maxLength={MAX_COUNTRY_LENGTH} {...field} />
                    </FormControl>
                    <p className="text-xs text-slate-500">
                      Jobs that require working on site or living in another country are rejected.
                    </p>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="languages"
                render={() => (
                  <FormItem>
                    <FormLabel>Languages you can work in</FormLabel>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      {languageChoices.map((language) => (
                        <label
                          key={language}
                          className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        >
                          <Checkbox
                            checked={selectedLanguages.includes(language)}
                            onCheckedChange={(checked) => toggleLanguage(language, checked === true)}
                          />
                          <span>{language}</span>
                        </label>
                      ))}
                    </div>
                    <div className="flex max-w-sm gap-2">
                      <Input
                        value={otherLanguage}
                        placeholder="Other language"
                        onChange={(event) => setOtherLanguage(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            event.preventDefault()
                            addOtherLanguage()
                          }
                        }}
                      />
                      <Button type="button" variant="outline" onClick={addOtherLanguage}>
                        Add
                      </Button>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

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
