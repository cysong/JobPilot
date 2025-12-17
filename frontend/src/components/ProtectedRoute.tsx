/**
 * Protected Route wrapper component
 * Redirects to login if user is not authenticated
 */
import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import type { Role } from '@/types/auth'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRole?: Role
}

export default function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const location = useLocation()
  const { isAuthenticated, isLoading, initialize, user } = useAuthStore()

  useEffect(() => {
    initialize()
  }, [initialize])

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  // Redirect to login if not authenticated (admin routes go to /admin/login)
  if (!isAuthenticated) {
    const redirectTo = requiredRole === 'ADMIN' ? '/admin/login' : '/login'
    return <Navigate to={redirectTo} state={{ from: location }} replace />
  }

  // Role guard (optional)
  if (requiredRole && user?.role !== requiredRole) {
    return <Navigate to="/dashboard" replace />
  }

  // Render protected content
  return <>{children}</>
}
