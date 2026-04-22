import { NavLink, Outlet } from 'react-router-dom'
import { Briefcase, KeyRound, UserRound } from 'lucide-react'

const navItems = [
  { to: '/settings/profile', label: 'Profile', icon: UserRound },
  { to: '/settings/account', label: 'Account', icon: KeyRound },
  { to: '/settings/preferences', label: 'Job Preferences', icon: Briefcase },
] as const

export default function SettingsLayout() {
  return (
    <div className="container mx-auto max-w-6xl p-6 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        <p className="mt-2 text-slate-600">
          Manage your identity, sign-in credentials, and job-search preferences.
        </p>
      </div>

      <div className="grid gap-8 md:grid-cols-[220px_1fr]">
        <nav className="flex flex-col gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
