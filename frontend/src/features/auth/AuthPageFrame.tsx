import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

interface AuthPageFrameProps {
  title: string
  description: string
  children: ReactNode
  footer?: ReactNode
}

export default function AuthPageFrame({
  title,
  description,
  children,
  footer,
}: AuthPageFrameProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-4xl grid lg:grid-cols-[1.1fr_0.9fr] gap-8 items-center">
        <div className="hidden lg:flex flex-col justify-center space-y-6 p-8">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center text-white">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <span className="font-bold text-2xl text-slate-900 tracking-tight">JobPilot</span>
          </div>
          <h1 className="text-4xl font-extrabold text-slate-900 leading-tight">{title}</h1>
          <p className="text-lg text-slate-600">{description}</p>
          <p className="text-sm text-slate-500">
            <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500 hover:underline">
              Back to sign in
            </Link>
          </p>
        </div>

        <Card className="w-full shadow-xl border-slate-200">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">{children}</CardContent>
          {footer ? <div className="px-6 pb-6">{footer}</div> : null}
        </Card>
      </div>
    </div>
  )
}
