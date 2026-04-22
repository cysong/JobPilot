import { STATUS_PALETTE } from '@/features/applications/statusPalette'
import type { Application, ApplicationStatus } from '@/types/application'

export type ApplicationMaterialKind = 'resume' | 'coverLetter'
export type ApplicationMaterialState = 'Pending' | 'Generating' | 'Ready' | 'Failed'

// Material states map to a subset of ApplicationStatus so they share palette colors.
const MATERIAL_STATE_TO_STATUS: Record<ApplicationMaterialState, ApplicationStatus> = {
  Pending: 'PENDING',
  Generating: 'TAILORING',
  Ready: 'READY',
  Failed: 'FAILED',
}

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
): string => STATUS_PALETTE[MATERIAL_STATE_TO_STATUS[state]].pillClass
