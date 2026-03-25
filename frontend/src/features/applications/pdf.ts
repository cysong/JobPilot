import { applicationApi } from '@/api/applications'
import { buildApplicationPdfFilename } from '@/utils/pdfFilename'

type ApplicationPdfKind = 'Resume' | 'CoverLetter'

type DownloadApplicationPdfParams = {
  applicationId: string
  kind: ApplicationPdfKind
  userName: string
  jobTitle: string
}

const triggerBrowserDownload = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}

export const downloadApplicationPdf = async ({
  applicationId,
  kind,
  userName,
  jobTitle,
}: DownloadApplicationPdfParams) => {
  const blob =
    kind === 'Resume'
      ? await applicationApi.exportTailoredResumePdf(applicationId)
      : await applicationApi.exportCoverLetterPdf(applicationId)

  const filename = buildApplicationPdfFilename({
    userName,
    label: kind,
    jobTitle,
  })

  triggerBrowserDownload(blob, filename)
}
