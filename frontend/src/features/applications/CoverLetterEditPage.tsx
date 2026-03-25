import { useParams } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useCoverLetterForEdit, useUpdateCoverLetterContent } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'
import { downloadApplicationPdf } from './pdf'

export default function CoverLetterEditPage() {
  const { applicationId } = useParams()
  const { user } = useAuthStore()
  const { data: documentData } = useCoverLetterForEdit(applicationId || '')

  const handleExportPdf = async (id: string, _title: string) => {
    await downloadApplicationPdf({
      applicationId: id,
      kind: 'CoverLetter',
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
      useDocument={useCoverLetterForEdit}
      useUpdateDocument={useUpdateCoverLetterContent}
      useExportPdf={handleExportPdf}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-coverletter"
      documentId={applicationId}
    />
  )
}
