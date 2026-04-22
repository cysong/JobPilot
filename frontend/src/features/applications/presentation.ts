import type { Application, ApplicationStatus } from '@/types/application'

export type ApplicationMaterialKind = 'resume' | 'coverLetter'
export type ApplicationMaterialState = 'Pending' | 'Generating' | 'Ready' | 'Failed'

type ApplicationMaterialSource = Pick<
  Application,
  'status' | 'resume_document_id' | 'cover_letter_document_id'
>

export const getApplicationMaterialState = (
  application: ApplicationMaterialSource,
  kind: ApplicationMaterialKind,
): ApplicationMaterialState => {
  if (application.status === 'TAILORING') return 'Generating'
  if (application.status === 'FAILED') return 'Failed'

  if (kind === 'resume') {
    return application.resume_document_id ? 'Ready' : 'Pending'
  }

  return application.cover_letter_document_id ? 'Ready' : 'Pending'
}

export const getApplicationMaterialEmptyMessage = (
  status: ApplicationStatus,
  kind: ApplicationMaterialKind,
): string => {
  const label = kind === 'resume' ? 'Resume' : 'Cover letter'

  if (status === 'FAILED') {
    return `${label} generation failed. Use Retry Generation in Operations to try again.`
  }

  if (status === 'TAILORING') {
    return kind === 'resume'
      ? 'Resume is currently being tailored for this application.'
      : 'Cover letter is currently being generated for this application.'
  }

  return `${label} is still being prepared for this application.`
}

export const getApplicationMaterialStateClassName = (
  state: ApplicationMaterialState,
): string => {
  switch (state) {
    case 'Ready':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700'
    case 'Generating':
      return 'border-sky-200 bg-sky-50 text-sky-700'
    case 'Failed':
      return 'border-red-200 bg-red-50 text-red-700'
    default:
      return 'border-slate-200 bg-slate-100 text-slate-500'
  }
}
