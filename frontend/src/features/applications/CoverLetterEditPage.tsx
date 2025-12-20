import { useParams } from 'react-router-dom'

import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useCoverLetterEdit, useUpdateCoverLetter } from './hooks/useApplications'

export default function CoverLetterEditPage() {
  const { applicationId } = useParams()

  return (
    <DocumentEditPage
      useDocument={useCoverLetterEdit}
      useUpdateDocument={useUpdateCoverLetter}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-coverletter"
    />
  )
}
