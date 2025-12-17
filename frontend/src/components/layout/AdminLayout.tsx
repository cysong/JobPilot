import { Outlet } from 'react-router-dom'
import { AdminNavigation } from '@/components/layout/AdminNavigation'

export default function AdminLayout() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <AdminNavigation />
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
