import { useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { FileCheck } from 'lucide-react'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import {
  useResumeEdit,
  useCreateResume,
  useUpdateResumeContent,
  useResumeMutations
} from '@/features/resumes/hooks/useResumes'
import { resumeApi } from '@/api/resumes'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'

export default function ResumeContentEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id || id === 'new'

  // Get Resume data (only for edit mode)
  const { data: resume } = useResumeEdit(isNew ? '' : id!)
  const { finalizeResume } = useResumeMutations()

  const handleExportPdf = async (id: string, title: string) => {
    const blob = await resumeApi.exportResume(id)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title}.pdf`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  const handleFinalize = useCallback(() => {
    if (id) {
      finalizeResume.mutate(id)
    }
  }, [id, finalizeResume])

  // Use useMemo to make config reactive to resume data changes
  const config: DocumentEditConfig = useMemo(() => ({
    mode: "auto", // Auto-detect create/edit based on URL
    fields: {
      title: {
        enabled: true,
        required: true,
        placeholder: "Resume Title...",
      },
      content: {
        enabled: true,
        required: true,
      },
    },
    ui: {
      showBusinessBadge: true,
      showExportPdf: true,
    },
    slots: {
      actionsBefore:
        !isNew && resume?.is_draft ? (
          <>
            <Badge
              variant="outline"
              className="bg-yellow-50 text-yellow-700 border-yellow-200"
            >
              Draft
            </Badge>
            <Button
              variant="outline"
              onClick={handleFinalize}
              className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
            >
              <FileCheck className="w-4 h-4 mr-2" />
              Finalize
            </Button>
          </>
        ) : null,
    },
    lifecycle: {
      onCreateSuccess: (newId: string) => {
        navigate(`/resumes/${newId}/edit`, { replace: true });
      },
    },
  }), [isNew, resume?.is_draft, handleFinalize, navigate]);

  return (
    <DocumentEditPage
      config={config}
      useDocument={useResumeEdit}
      useCreateDocument={useCreateResume}
      useUpdateDocument={useUpdateResumeContent}
      useExportPdf={handleExportPdf}
      returnPath="/resumes"
      storageKeyPrefix="resume"
    />
  )
}
