import { Link, useLocation } from 'react-router-dom'
import { UserNav } from './UserNav'
import { MobileNav } from './MobileNav'
import { cn } from '@/utils/cn'

export function Navigation() {
    const location = useLocation()

    const navLinks = [
        { href: '/dashboard', label: 'Dashboard' },
        { href: '/jobs', label: 'Jobs' },
        { href: '/applications', label: 'Applications' },
        { href: '/resumes', label: 'Resumes' },
        { href: '/skills', label: 'Skills' },
    ]

    return (
        <nav className="bg-white border-b border-slate-200 px-6 py-3 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto flex justify-between items-center">
                <div className="flex items-center gap-8">
                    {/* Logo */}
                    <Link to="/" className="flex items-center gap-2 group">
                        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white group-hover:bg-indigo-700 transition-colors">
                            <svg
                                className="w-5 h-5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth="2"
                                    d="M13 10V3L4 14h7v7l9-11h-7z"
                                ></path>
                            </svg>
                        </div>
                        <span className="font-bold text-xl text-slate-900 tracking-tight">
                            JobPilot
                        </span>
                    </Link>

                    {/* Desktop Nav */}
                    <div className="hidden md:flex gap-6 text-sm font-medium text-slate-600">
                        {navLinks.map((link) => (
                            <Link
                                key={link.href}
                                to={link.href}
                                className={cn(
                                    "transition-colors hover:text-indigo-600",
                                    location.pathname.startsWith(link.href)
                                        ? "text-indigo-600 font-semibold"
                                        : "text-slate-600"
                                )}
                            >
                                {link.label}
                            </Link>
                        ))}
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <UserNav />
                    <MobileNav />
                </div>
            </div>
        </nav>
    )
}
