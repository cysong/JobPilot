import { Outlet } from 'react-router-dom'
import { Navigation } from '@/components/layout/Navigation'

/**
 * Layout for pages that need the full viewport width (document editors, etc.)
 * Keeps the shared navigation while removing the max-width container.
 */
export default function FullWidthLayout() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navigation />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}
