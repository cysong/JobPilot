import type { ReactNode } from 'react'
import type { UseQueryResult, UseMutationResult } from '@tanstack/react-query'
import type { DocumentEditData } from '@/types/document'

// Field configuration
export interface FieldConfig {
  enabled: boolean
  required?: boolean
  placeholder?: string
  validation?: (value: string) => boolean | string
}

// Document edit configuration
export interface DocumentEditConfig<TData = any> {
  // Mode control
  mode?: 'edit' | 'create' | 'auto'  // auto: auto-detect based on id

  // Field configuration
  fields: {
    title?: FieldConfig
    content: FieldConfig
  }

  // UI configuration
  ui?: {
    showBusinessBadge?: boolean
    showExportPdf?: boolean
  }

  // Extension slots (Composition pattern)
  slots?: {
    headerExtra?: ReactNode          // Extra content in header
    actionsBefore?: ReactNode        // Actions before save button
    actionsAfter?: ReactNode         // Actions after save button
  }

  // Lifecycle hooks
  lifecycle?: {
    onBeforeSave?: (data: TData) => TData | Promise<TData>
    onAfterSave?: (data: TData) => void
    onCreateSuccess?: (id: string, data: TData) => void
  }
}

// Component props
export interface DocumentEditPageProps<TData = any> {
  // Configuration
  config: DocumentEditConfig<TData>

  // API hooks
  useDocument: (id: string) => UseQueryResult<DocumentEditData>
  useCreateDocument?: () => UseMutationResult<any, unknown, TData, unknown>
  useUpdateDocument: () => UseMutationResult<any, unknown, { id: string } & TData, unknown>

  // Optional features
  useExportPdf?: (id: string, title: string) => Promise<void>
  onTitleSave?: (id: string, title: string) => Promise<void>

  // Navigation
  returnPath: string

  // Local storage
  storageKeyPrefix: string

  // Document ID (optional, if not provided will use URL param 'id')
  documentId?: string
}
