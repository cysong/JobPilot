export type BusinessDocumentType = 'resume' | 'tailored_resume' | 'cover_letter'

export interface DocumentEditData {
  business_type: BusinessDocumentType
  business_id: string
  title: string

  document_id: string
  content: string
  format: string

  created_at: string
  updated_at: string

  job_title?: string | null
  company_name?: string | null
  source_resume_title?: string | null
}

export interface DocumentUpdatePayload {
  content: string
  change_comments?: string | null
}
