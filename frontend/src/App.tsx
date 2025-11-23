import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from '@/features/auth/Login'
import Register from '@/features/auth/Register'
import ProtectedRoute from '@/components/ProtectedRoute'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// Temporary home page component (will be replaced with actual Jobs page later)
function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">JobPilot</h1>
          <p className="mt-1 text-sm text-gray-600">AI-powered job application assistant</p>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-semibold text-gray-800 mb-4">
            Welcome! 🚀
          </h2>
          <p className="text-gray-600">
            You are successfully logged in to JobPilot.
          </p>
          <div className="mt-4 text-sm text-gray-500">
            <p>✅ Authentication System Complete</p>
            <p>✅ Protected Routes Working</p>
            <p>✅ JWT Token Management</p>
          </div>
        </div>
      </main>
    </div>
  )
}

import { Toaster } from '@/components/ui/toaster'

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes */}
          <Route
            path="/jobs"
            element={
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            }
          />

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/jobs" replace />} />

          {/* Catch-all redirect to home */}
          <Route path="*" element={<Navigate to="/jobs" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  )
}

export default App
