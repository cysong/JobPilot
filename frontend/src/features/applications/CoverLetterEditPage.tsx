import { useParams } from 'react-router-dom'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useCoverLetterForEdit, useUpdateCoverLetterContent } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'

export default function CoverLetterEditPage() {
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
      useDocument={useCoverLetterForEdit}
      useUpdateDocument={useUpdateCoverLetterContent}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-coverletter"
      documentId={applicationId}
    />
  )
}
