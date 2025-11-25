import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from '@/features/auth/Login'
import Register from '@/features/auth/Register'
import ProtectedRoute from '@/components/ProtectedRoute'
import MainLayout from '@/components/layout/MainLayout'
import LandingPage from '@/features/landing/LandingPage'
import PlaceholderPage from '@/features/common/PlaceholderPage'
import JobListingPage from '@/features/jobs/JobListingPage'
import JobDetailPage from '@/features/jobs/JobDetailPage'
import ApplicationListingPage from '@/features/applications/ApplicationListingPage'
import ResumeListingPage from '@/features/resumes/ResumeListingPage'
import ResumeEditPage from '@/features/resumes/ResumeEditPage'
import { Toaster } from '@/components/ui/toaster'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

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
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<PlaceholderPage />} />
            <Route path="/jobs" element={<JobListingPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/applications" element={<ApplicationListingPage />} />
            <Route path="/resumes" element={<ResumeListingPage />} />
            <Route path="/resumes/new" element={<ResumeEditPage />} />
            <Route path="/resumes/:id" element={<ResumeEditPage />} />
            <Route path="/profile" element={<PlaceholderPage />} />
            <Route path="/settings" element={<PlaceholderPage />} />
          </Route>

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  )
}

export default App
