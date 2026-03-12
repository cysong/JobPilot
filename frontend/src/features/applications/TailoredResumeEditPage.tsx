import { useParams } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { applicationApi } from '@/api/applications'
import { useTailoredResumeForEdit, useUpdateTailoredResumeContent } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'
import { buildApplicationPdfFilename } from '@/utils/pdfFilename'

export default function TailoredResumeEditPage() {
  const { applicationId } = useParams()
  const { user } = useAuthStore()
  const { data: documentData } = useTailoredResumeForEdit(applicationId || '')

  const handleExportPdf = async (id: string, _title: string) => {
    const blob = await applicationApi.exportTailoredResumePdf(id)
    const url = window.URL.createObjectURL(blob)
    const jobTitle = documentData?.job_title || 'Job'
    const userName = user?.full_name || 'User'
    const filename = buildApplicationPdfFilename({ userName, label: 'Resume', jobTitle })
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  const config: DocumentEditConfig = {
    mode: 'edit',  // Edit-only mode
    fields: {
      title: {
        enabled: false  // Title is not editable
      },
      content: {
        enabled: true,
        required: true
      }
    },
    ui: {
      showBusinessBadge: false,
      showExportPdf: true
    }
  }

  return (
    <DocumentEditPage
      config={config}
      useDocument={useTailoredResumeForEdit}
      useUpdateDocument={useUpdateTailoredResumeContent}
      useExportPdf={handleExportPdf}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-resume"
      documentId={applicationId}
    />
  )
}
