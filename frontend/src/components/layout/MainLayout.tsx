import { Outlet } from 'react-router-dom'
import { Navigation } from '@/components/layout/Navigation'

export default function MainLayout() {
    return (
        <div className="min-h-screen bg-slate-50 flex flex-col">
            <Navigation />
            <main className="flex-1">
                <Outlet />
            </main>
        </div>
    )
}
