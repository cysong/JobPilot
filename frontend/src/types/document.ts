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
  is_draft?: boolean
}

export interface DocumentUpdatePayload {
  content: string
  title?: string  // Optional: only for documents that allow title editing (e.g., resumes)
  change_comments?: string | null
}
