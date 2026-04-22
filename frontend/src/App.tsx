import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from '@/features/auth/Login'
import Register from '@/features/auth/Register'
import ForgotPassword from '@/features/auth/ForgotPassword'
import ResetPassword from '@/features/auth/ResetPassword'
import VerifyEmail from '@/features/auth/VerifyEmail'
import ChangeEmailConfirmPage from '@/features/auth/ChangeEmailConfirmPage'
import ProtectedRoute from '@/components/ProtectedRoute'
import MainLayout from '@/components/layout/MainLayout'
import FullWidthLayout from '@/components/layout/FullWidthLayout'
import AdminLayout from '@/components/layout/AdminLayout'
import LandingPage from '@/features/landing/LandingPage'
import SettingsLayout from '@/features/settings/SettingsLayout'
import SettingsProfilePage from '@/features/settings/ProfilePage'
import SettingsAccountPage from '@/features/settings/AccountPage'
import SettingsJobPreferencesPage from '@/features/settings/JobPreferencesPage'
import UserDashboardPage from '@/features/dashboard/UserDashboardPage'
import JobListingPage from '@/features/jobs/JobListingPage'
import JobDetailPage from '@/features/jobs/JobDetailPage'
import ApplicationListingPage from '@/features/applications/ApplicationListingPage'
import ApplicationDetailPage from '@/features/applications/ApplicationDetailPage'
import ResumeListingPage from '@/features/resumes/ResumeListingPage'
import ResumeEditPage from '@/features/resumes/ResumeEditPage'
import TailoredResumeEditPage from '@/features/applications/TailoredResumeEditPage'
import CoverLetterEditPage from '@/features/applications/CoverLetterEditPage'
import { SkillsPage } from '@/features/skills/SkillsPage'
import AdminDashboardPage from '@/features/admin/pages/AdminDashboardPage'
import TaskMonitorPage from '@/features/admin/pages/TaskMonitorPage'
import AdminJobsChartPage from '@/features/admin/pages/AdminJobsChartPage'
import AdminAIUsageChartPage from '@/features/admin/pages/AdminAIUsageChartPage'
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
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/change-email-confirm" element={<ChangeEmailConfirmPage />} />

          {/* Protected routes - standard layout */}
          <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<UserDashboardPage />} />
            <Route path="/jobs" element={<JobListingPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/applications" element={<ApplicationListingPage />} />
            <Route path="/applications/:applicationId" element={<ApplicationDetailPage />} />
            <Route path="/resumes" element={<ResumeListingPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/profile" element={<Navigate to="/settings/preferences" replace />} />
            <Route path="/settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="profile" replace />} />
              <Route path="profile" element={<SettingsProfilePage />} />
              <Route path="account" element={<SettingsAccountPage />} />
              <Route path="preferences" element={<SettingsJobPreferencesPage />} />
              <Route path="security" element={<Navigate to="../account" replace />} />
            </Route>
          </Route>

          {/* Protected routes - full width layout (document editors) */}
          <Route element={<ProtectedRoute><FullWidthLayout /></ProtectedRoute>}>
            <Route path="/applications/:applicationId/resume" element={<TailoredResumeEditPage />} />
            <Route path="/applications/:applicationId/cover-letter" element={<CoverLetterEditPage />} />
            <Route path="/resumes/new" element={<ResumeEditPage />} />
            <Route path="/resumes/:id" element={<ResumeEditPage />} />
          </Route>

          {/* Admin protected routes */}
          <Route element={<ProtectedRoute requiredRole={Role.ADMIN}><AdminLayout /></ProtectedRoute>}>
            <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
            <Route path="/admin/jobs/chart" element={<AdminJobsChartPage />} />
            <Route path="/admin/ai/charts" element={<AdminAIUsageChartPage />} />
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
