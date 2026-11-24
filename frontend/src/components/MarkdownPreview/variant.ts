import type { BusinessDocumentType } from '@/types/document'

/**
 * `resume` renders the markdown the way the PDF "modern" template does (see
 * styles.css); `default` is generic prose styling for other documents.
 */
export type MarkdownPreviewVariant = 'resume' | 'default'

/** Resumes (base and tailored) preview like the PDF; cover letters use prose. */
export function previewVariantFor(businessType?: BusinessDocumentType): MarkdownPreviewVariant {
  return businessType === 'resume' || businessType === 'tailored_resume' ? 'resume' : 'default'
}
