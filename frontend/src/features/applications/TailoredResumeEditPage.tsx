import { useParams } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useTailoredResumeForEdit, useUpdateTailoredResumeContent } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'
import { downloadApplicationPdf } from './pdf'

export default function TailoredResumeEditPage() {
  const { applicationId } = useParams()
  const { user } = useAuthStore()
  const { data: documentData } = useTailoredResumeForEdit(applicationId || '')

  const handleExportPdf = async (id: string, _title: string) => {
    await downloadApplicationPdf({
      applicationId: id,
      kind: 'Resume',
      userName: user?.full_name || 'User',
      jobTitle: documentData?.job_title || 'Job',
    })
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
