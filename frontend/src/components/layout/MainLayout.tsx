import { Outlet, useLocation, matchPath } from 'react-router-dom'
import { Navigation } from '@/components/layout/Navigation'

export default function MainLayout() {
    const location = useLocation()

    // Pages that should take full width (no container constraints)
    const isFullWidthPage = matchPath('/resumes/:id', location.pathname) ||
        location.pathname === '/resumes/new'

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col">
            <Navigation />
            <main className={`flex-1 ${!isFullWidthPage ? 'max-w-7xl w-full mx-auto px-6 py-8' : ''}`}>
                <Outlet />
            </main>
        </div>
    )
}
