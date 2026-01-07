import { useParams } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { applicationApi } from '@/api/applications'
import { useCoverLetterForEdit, useUpdateCoverLetterContent } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'

const toSafeFilename = (value: string) => {
  const cleaned = value.replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '')
  return cleaned || 'document'
}

export default function CoverLetterEditPage() {
  const { applicationId } = useParams()
  const { user } = useAuthStore()
  const { data: documentData } = useCoverLetterForEdit(applicationId || '')

  const handleExportPdf = async (id: string, _title: string) => {
    const blob = await applicationApi.exportCoverLetterPdf(id)
    const url = window.URL.createObjectURL(blob)
    const jobTitle = documentData?.job_title || 'Job'
    const userName = user?.full_name || 'User'
    const filename = `${toSafeFilename(`${userName}_CoverLetter_${jobTitle}`)}.pdf`
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
      useDocument={useCoverLetterForEdit}
      useUpdateDocument={useUpdateCoverLetterContent}
      useExportPdf={handleExportPdf}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-coverletter"
      documentId={applicationId}
    />
  )
}
