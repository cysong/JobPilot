import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from '@/features/auth/Login'
import Register from '@/features/auth/Register'
import ProtectedRoute from '@/components/ProtectedRoute'
import MainLayout from '@/components/layout/MainLayout'
import FullWidthLayout from '@/components/layout/FullWidthLayout'
import AdminLayout from '@/components/layout/AdminLayout'
import LandingPage from '@/features/landing/LandingPage'
import PlaceholderPage from '@/features/common/PlaceholderPage'
import JobListingPage from '@/features/jobs/JobListingPage'
import JobDetailPage from '@/features/jobs/JobDetailPage'
import ApplicationListingPage from '@/features/applications/ApplicationListingPage'
import ApplicationDetailPage from '@/features/applications/ApplicationDetailPage'
import ResumeListingPage from '@/features/resumes/ResumeListingPage'
import ResumeEditPage from '@/features/resumes/ResumeEditPage'
import ResumeContentEditPage from '@/features/resumes/ResumeContentEditPage'
import TailoredResumeEditPage from '@/features/applications/TailoredResumeEditPage'
import CoverLetterEditPage from '@/features/applications/CoverLetterEditPage'
import { SkillsPage } from '@/features/skills/SkillsPage'
import AdminDashboardPage from '@/features/admin/pages/AdminDashboardPage'
import TaskMonitorPage from '@/features/admin/pages/TaskMonitorPage'
import { Role } from '@/types/auth'
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
          <Route path="/admin/login" element={<Login redirectPath="/admin/dashboard" />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes - standard layout */}
          <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<PlaceholderPage />} />
            <Route path="/jobs" element={<JobListingPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/applications" element={<ApplicationListingPage />} />
            <Route path="/applications/:applicationId" element={<ApplicationDetailPage />} />
            <Route path="/resumes" element={<ResumeListingPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/profile" element={<PlaceholderPage />} />
            <Route path="/settings" element={<PlaceholderPage />} />
          </Route>

          {/* Protected routes - full width layout (document editors) */}
          <Route element={<ProtectedRoute><FullWidthLayout /></ProtectedRoute>}>
            <Route path="/applications/:applicationId/resume/edit" element={<TailoredResumeEditPage />} />
            <Route path="/applications/:applicationId/cover-letter/edit" element={<CoverLetterEditPage />} />
            <Route path="/resumes/:id/edit" element={<ResumeContentEditPage />} />
            <Route path="/resumes/new" element={<ResumeEditPage />} />
            <Route path="/resumes/:id" element={<ResumeEditPage />} />
          </Route>

          {/* Admin protected routes */}
          <Route element={<ProtectedRoute requiredRole={Role.ADMIN}><AdminLayout /></ProtectedRoute>}>
            <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
            <Route path="/admin/tasks" element={<TaskMonitorPage />} />
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
