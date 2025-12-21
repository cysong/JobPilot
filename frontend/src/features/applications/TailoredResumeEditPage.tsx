import { useParams } from 'react-router-dom'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useTailoredResumeEdit, useUpdateTailoredResume } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'

export default function TailoredResumeEditPage() {
  const { applicationId } = useParams()

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
      showExportPdf: false
    }
  }

  return (
    <DocumentEditPage
      config={config}
      useDocument={useTailoredResumeEdit}
      useUpdateDocument={useUpdateTailoredResume}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-resume"
      documentId={applicationId}
    />
  )
}
