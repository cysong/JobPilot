import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Menu, Briefcase, LayoutDashboard, FileText, Send, Award } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from '@/components/ui/sheet'
import { cn } from '@/utils/cn'

interface NavItem {
    title: string
    href: string
    icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
    {
        title: 'Dashboard',
        href: '/dashboard',
        icon: LayoutDashboard,
    },
    {
        title: 'Jobs',
        href: '/jobs',
        icon: Briefcase,
    },
    {
        title: 'Applications',
        href: '/applications',
        icon: Send,
    },
    {
        title: 'Resumes',
        href: '/resumes',
        icon: FileText,
    },
    {
        title: 'Skills',
        href: '/skills',
        icon: Award,
    },
]

export function MobileNav() {
    const [open, setOpen] = useState(false)
    const location = useLocation()

    return (
        <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                    <Menu className="h-5 w-5" />
                    <span className="sr-only">Toggle menu</span>
                </Button>
            </SheetTrigger>
            <SheetContent side="left" className="pr-0">
                <SheetHeader className="px-1">
                    <SheetTitle className="text-left flex items-center gap-2">
                        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white">
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
                    </SheetTitle>
                </SheetHeader>
                <div className="flex flex-col space-y-3 mt-8">
                    {navItems.map((item) => {
                        const Icon = item.icon
                        const isActive = location.pathname.startsWith(item.href)
                        return (
                            <Link
                                key={item.href}
                                to={item.href}
                                onClick={() => setOpen(false)}
                                className={cn(
                                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                    isActive
                                        ? "bg-indigo-50 text-indigo-600"
                                        : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                                )}
                            >
                                <Icon className="h-5 w-5" />
                                {item.title}
                            </Link>
                        )
                    })}
                </div>
            </SheetContent>
        </Sheet>
    )
}
