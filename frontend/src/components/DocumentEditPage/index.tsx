import { useEffect, useMemo, useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, Download } from 'lucide-react'
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { MarkdownEditor } from '@/components/MarkdownEditor'
import { MarkdownPreview } from '@/components/MarkdownPreview'
import { useAutoSave } from '@/hooks/useAutoSave'
import type { DocumentEditData, DocumentUpdatePayload } from '@/types/document'

type UpdateVariables = { id: string } & DocumentUpdatePayload

type UseDocumentHook = (id: string) => UseQueryResult<DocumentEditData>
type UseUpdateDocumentHook = () => UseMutationResult<any, unknown, UpdateVariables, unknown>

interface DocumentEditPageProps {
  useDocument: UseDocumentHook
  useUpdateDocument: UseUpdateDocumentHook
  returnPath: string
  storageKeyPrefix: string
  useExportPdf?: (id: string, title: string) => Promise<void>
}

interface FormValues {
  content: string
  change_comments?: string
}

export function DocumentEditPage({
  useDocument,
  useUpdateDocument,
  returnPath,
  storageKeyPrefix,
  useExportPdf,
}: DocumentEditPageProps) {
  const params = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()

  const entityId = useMemo(() => params.id || params.applicationId, [params.id, params.applicationId])
  const { data: document, isLoading } = useDocument(entityId || '')
  const updateMutation = useUpdateDocument()

  const form = useForm<FormValues>({
    defaultValues: { content: '', change_comments: '' },
  })

  const storageKey = useMemo(() => {
    if (!document && !entityId) return undefined
    const id = document?.business_id || entityId
    return `${storageKeyPrefix}-${id}`
  }, [document?.business_id, entityId, storageKeyPrefix])

  // Load data and possibly restore draft
  useEffect(() => {
    if (!document) return
    const savedDraftRaw = storageKey ? localStorage.getItem(storageKey) : null

    if (savedDraftRaw) {
      try {
        const draft = JSON.parse(savedDraftRaw)
        const draftTime = draft.savedAt ? new Date(draft.savedAt).getTime() : 0
        const serverTime = document.updated_at ? new Date(document.updated_at).getTime() : 0

        if (draftTime > serverTime && draft.content) {
          form.setValue('content', draft.content, { shouldDirty: true })
        } else {
          form.reset({ content: document.content })
          localStorage.removeItem(storageKey!)
        }
      } catch {
        form.reset({ content: document.content })
        localStorage.removeItem(storageKey!)
      }
    } else {
      form.reset({ content: document.content })
    }
  }, [document, form, storageKey])

  // Auto-save to localStorage only
  const watchedContent = form.watch('content')
  const noopSave = useCallback(() => {}, [])
  useAutoSave({
    data: { content: watchedContent },
    onSave: noopSave,
    storageKey,
    enabled: !!document,
    interval: 4000,
  })

  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit')

  const handleSubmit = useCallback(
    (values: FormValues) => {
      if (!entityId) return
      if (!values.content.trim()) {
        toast({
          title: 'Content is required',
          description: 'Please add some content before saving.',
          variant: 'destructive',
        })
        return
      }

      updateMutation.mutate(
        { id: entityId, content: values.content, change_comments: values.change_comments },
        {
          onSuccess: () => {
            if (storageKey) localStorage.removeItem(storageKey)
            toast({ title: 'Saved successfully' })
            form.reset(values)
          },
          onError: () => {
            toast({
              title: 'Save failed',
              description: 'Please try again',
              variant: 'destructive',
            })
          },
        }
      )
    },
    [entityId, form, storageKey, toast, updateMutation]
  )

  // Ctrl/Cmd + S support
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        form.handleSubmit(handleSubmit)()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [form, handleSubmit])

  const handleExportPdf = async () => {
    if (!useExportPdf || !document || !entityId) return
    try {
      await useExportPdf(entityId, document.title)
    } catch {
      toast({
        title: 'Export failed',
        description: 'Failed to export PDF',
        variant: 'destructive',
      })
    }
  }

  if (!entityId) {
    return <div className="p-8">Invalid document</div>
  }

  if (isLoading) {
    return <div className="p-8">Loading...</div>
  }

  if (!document) {
    return <div className="p-8">Document not found</div>
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(returnPath)}>
            <ArrowLeft className="w-4 h-4" />
          </Button>

          <div>
            <h1 className="text-lg font-semibold">{document.title}</h1>
            {document.job_title && (
              <p className="text-sm text-slate-500">
                {document.company_name ? `${document.company_name} · ` : ''}
                {document.job_title}
              </p>
            )}
          </div>

          {document.business_type !== 'resume' && (
            <Badge variant="outline" className="bg-indigo-50 text-indigo-700">
              {document.business_type === 'tailored_resume' ? 'Tailored Resume' : 'Cover Letter'}
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Tab Switcher */}
          <div className="bg-slate-100 p-1 rounded-lg flex mr-4">
            <button
              onClick={() => setActiveTab('edit')}
              className={`px-3 py-1.5 rounded transition-all ${
                activeTab === 'edit' ? 'bg-white shadow-sm' : ''
              }`}
            >
              Edit
            </button>
            <button
              onClick={() => setActiveTab('preview')}
              className={`px-3 py-1.5 rounded transition-all ${
                activeTab === 'preview' ? 'bg-white shadow-sm' : ''
              }`}
            >
              Preview
            </button>
          </div>

          {useExportPdf && (
            <Button variant="outline" onClick={handleExportPdf}>
              <Download className="w-4 h-4 mr-2" />
              Export PDF
            </Button>
          )}

          <Button
            onClick={form.handleSubmit(handleSubmit)}
            disabled={!form.formState.isDirty || updateMutation.isPending}
          >
            <Save className="w-4 h-4 mr-2" />
            {updateMutation.isPending ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </div>

      {/* Editor/Preview Area */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'edit' ? (
          <div className="h-full flex">
            {/* Editor Column */}
            <div className="w-1/2 border-r flex flex-col">
              <div className="border-b px-6 py-3 bg-slate-50">
                <span className="text-xs font-semibold text-slate-500 uppercase">
                  Markdown Editor
                </span>
              </div>
              <div className="flex-1 overflow-auto">
                <MarkdownEditor
                  content={form.watch('content')}
                  onChange={(value) => form.setValue('content', value, { shouldDirty: true })}
                />
              </div>
            </div>

            {/* Preview Column */}
            <div className="w-1/2 flex flex-col">
              <div className="border-b px-6 py-3 bg-slate-50">
                <span className="text-xs font-semibold text-slate-500 uppercase">
                  Live Preview
                </span>
              </div>
              <div className="flex-1 overflow-auto bg-slate-50 p-8">
                <div className="bg-white shadow-sm border min-h-[297mm] w-[210mm] mx-auto">
                  <MarkdownPreview content={form.watch('content')} />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full overflow-auto bg-slate-50 p-8 flex justify-center">
            <div className="bg-white shadow-sm border min-h-[297mm] w-[210mm]">
              <MarkdownPreview content={form.watch('content')} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
