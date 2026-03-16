import { Link } from 'react-router-dom'
import { ArrowUpRight, Award, Briefcase, Send, UserRound } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const links = [
  {
    href: '/jobs',
    label: 'Browse Jobs',
    description: 'Review fresh listings and matches',
    icon: Briefcase,
  },
  {
    href: '/applications',
    label: 'My Applications',
    description: 'Track statuses and materials',
    icon: Send,
  },
  {
    href: '/resumes',
    label: 'My Resumes',
    description: 'Edit, finalize, and export templates',
    icon: UserRound,
  },
  {
    href: '/skills',
    label: 'My Skills',
    description: 'Keep matching data current',
    icon: Award,
  },
]

export function QuickLinksCard() {
  return (
    <Card className="rounded-3xl border-slate-200 shadow-sm">
      <CardHeader>
        <div className="text-sm font-medium text-slate-500">Quick Access</div>
        <CardTitle className="text-xl text-slate-950">Jump Back In</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {links.map((link) => {
          const Icon = link.icon
          return (
            <Link
              key={link.href}
              to={link.href}
              className="flex items-center justify-between rounded-2xl border border-slate-200 p-4 transition-colors hover:border-indigo-200 hover:bg-indigo-50/60"
            >
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-slate-100 p-2 text-slate-700">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="space-y-1">
                  <div className="font-medium text-slate-900">{link.label}</div>
                  <div className="text-sm text-slate-600">{link.description}</div>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-slate-400" />
            </Link>
          )
        })}
      </CardContent>
    </Card>
  )
}
