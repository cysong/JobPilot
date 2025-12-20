import { DocumentEditPage } from '@/components/DocumentEditPage'
import { resumeApi } from '@/api/resumes'
import { useResumeEdit, useUpdateResumeContent } from '@/features/resumes/hooks/useResumes'

export default function ResumeContentEditPage() {
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

  return (
    <DocumentEditPage
      useDocument={useResumeEdit}
      useUpdateDocument={useUpdateResumeContent}
      useExportPdf={handleExportPdf}
      returnPath="/resumes"
      storageKeyPrefix="resume"
    />
  )
}
