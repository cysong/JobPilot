import { Link } from 'react-router-dom'
import { ArrowRight, Briefcase, UserRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

interface DashboardHeroProps {
  userName: string
  message: string
  isLoading: boolean
}

export function DashboardHero({ userName, message, isLoading }: DashboardHeroProps) {
  if (isLoading) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="mt-4 h-10 w-72" />
        <Skeleton className="mt-3 h-5 w-full max-w-2xl" />
        <div className="mt-6 flex gap-3">
          <Skeleton className="h-11 w-32" />
          <Skeleton className="h-11 w-36" />
        </div>
      </div>
    )
  }

  return (
    <section className="relative overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-white via-white to-indigo-50 p-8 shadow-sm">
      <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-indigo-100/70 blur-3xl" />
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl space-y-3">
          <div className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-indigo-700">
            JobPilot, Your Job-Seeking Co-Pilot
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
              Welcome back, {userName}
            </h1>
            <p className="max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">
              {message}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg" className="bg-indigo-600 hover:bg-indigo-700">
            <Link to="/jobs">
              <Briefcase className="mr-2 h-4 w-4" />
              Browse Jobs
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/resumes">
              <UserRound className="mr-2 h-4 w-4" />
              Manage Resumes
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  )
}
