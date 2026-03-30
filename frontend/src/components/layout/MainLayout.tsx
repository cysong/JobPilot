import { Outlet } from 'react-router-dom'
import { EmailVerificationBanner } from '@/components/layout/EmailVerificationBanner'
import { Navigation } from '@/components/layout/Navigation'

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navigation />
      <EmailVerificationBanner />
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
