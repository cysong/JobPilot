import { useParams } from 'react-router-dom'

import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useTailoredResumeEdit, useUpdateTailoredResume } from './hooks/useApplications'

export default function TailoredResumeEditPage() {
  const { applicationId } = useParams()

  return (
    <DocumentEditPage
      useDocument={useTailoredResumeEdit}
      useUpdateDocument={useUpdateTailoredResume}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-resume"
    />
  )
}
