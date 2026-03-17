import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { ArrowLeft, Save, Download, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { MarkdownEditor } from '@/components/MarkdownEditor'
import { MarkdownPreview } from '@/components/MarkdownPreview'
import { useAutoSave } from '@/hooks/useAutoSave'
import type { DocumentEditPageProps } from './types'

export function DocumentEditPage<TData = any>({
  config,
  useDocument,
  useCreateDocument,
  useUpdateDocument,
  useExportPdf,
  onTitleSave,
  returnPath,
  storageKeyPrefix,
  documentId
}: DocumentEditPageProps<TData>) {
  const { id: urlId } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit')
  const [isExporting, setIsExporting] = useState(false)

  // Use documentId prop if provided, otherwise fall back to URL param
  const id = documentId || urlId

  // Determine mode
  const mode = useMemo(() => {
    if (config.mode === 'auto') {
      return id && id !== 'new' ? 'edit' : 'create'
    }
    return config.mode || 'edit'
  }, [config.mode, id])

  const isCreating = mode === 'create'

  // Fetch document (only in edit mode)
  const { data: document, isLoading } = useDocument(
    !isCreating && id ? id : ''
  )

  const updateMutation = useUpdateDocument()
  const createMutation = useCreateDocument?.()

  // Form management
  const form = useForm({
    defaultValues: {
      title: '',
      content: ''
    }
  })

  // Storage key
  const storageKey = useMemo(() => {
    const docId = isCreating ? 'new' : (document?.business_id || id)
    return docId ? `${storageKeyPrefix}-${docId}` : undefined
  }, [storageKeyPrefix, document?.business_id, id, isCreating])

  // Load document data and check for local draft
  useEffect(() => {
    if (isCreating) {
      // Create mode: check for local draft
      if (storageKey) {
        const savedDraft = localStorage.getItem(storageKey)
        if (savedDraft) {
          try {
            const draft = JSON.parse(savedDraft)
            toast({
              title: "Unsaved Draft",
              description: "Restoring your previous work...",
            })
            form.setValue('content', draft.content || '', { shouldDirty: true })
          } catch {
            localStorage.removeItem(storageKey)
          }
        }
      }
      return
    }

    if (!document) return

    const savedDraft = storageKey ? localStorage.getItem(storageKey) : null

    // Always load server data first
    form.reset({
      title: document.title,
      content: document.content
    })

    // Check for newer local draft
    if (savedDraft) {
      try {
        const draft = JSON.parse(savedDraft)
        const draftTime = draft.savedAt ? new Date(draft.savedAt).getTime() : 0
        const serverTime = document.updated_at ? new Date(document.updated_at).getTime() : 0

        const getStringValue = (value: unknown) => (
          typeof value === 'string' ? value : ''
        )
        const serverContent = getStringValue(document.content)
        const draftContent = getStringValue(draft.content)
        const contentChanged = draftContent !== serverContent
        const draftHasChanges = contentChanged && draftContent.length > 0

        if (draftTime > serverTime && draftHasChanges) {
          toast({
            title: "Unsaved Changes Found",
            description: "Would you like to restore your unsaved work?",
            action: (
              <Button
                size="sm"
                onClick={() => {
                  if (typeof draft.content === 'string') {
                    form.setValue('content', draft.content, { shouldDirty: true })
                  }
                  toast({ title: "Draft Restored" })
                }}
              >
                Restore
              </Button>
            ),
          })
        } else {
          localStorage.removeItem(storageKey!)
        }
      } catch {
        localStorage.removeItem(storageKey!)
      }
    }
  }, [document, form, toast, storageKey, isCreating])

  // Auto-save to localStorage
  const watchedValues = form.watch()
  const isContentDirty = form.getFieldState('content', form.formState).isDirty
  const isSaving = Boolean(updateMutation?.isPending || createMutation?.isPending)
  const canSave = isContentDirty && !isSaving
  const noopSave = useCallback(() => {}, [])
  useAutoSave({
    data: { content: watchedValues.content },
    onSave: noopSave,
    storageKey,
    enabled: isContentDirty,
    interval: 4000,
  })

  const handleTitleBlur = useCallback(async () => {
    if (!onTitleSave || !config.fields.title?.enabled || isCreating || !id || !document) {
      return
    }

    const title = form.getValues('title').trim()
    const serverTitle = typeof document.title === 'string' ? document.title : ''

    if (config.fields.title.required && !title) {
      toast({
        title: 'Validation Error',
        description: 'Title cannot be empty',
        variant: 'destructive'
      })
      form.setValue('title', serverTitle, { shouldDirty: false })
      return
    }

    if (!title || title === serverTitle) {
      return
    }

    try {
      await onTitleSave(id, title)
    } catch {
      toast({
        title: 'Title save failed',
        description: 'Please try again',
        variant: 'destructive'
      })
      form.setValue('title', serverTitle, { shouldDirty: false })
    }
  }, [onTitleSave, config.fields.title, isCreating, id, document, form, toast])

  // Submit handler
  const handleSubmit = useCallback(async (values: any) => {
    if (!canSave) {
      return
    }

    // Validation
    if (!values.content?.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Content cannot be empty',
        variant: 'destructive'
      })
      return
    }

    if (config.fields.title?.enabled && config.fields.title.required && !values.title?.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Title cannot be empty',
        variant: 'destructive'
      })
      return
    }

    // Lifecycle hook
    let processedData = values
    if (config.lifecycle?.onBeforeSave) {
      processedData = await config.lifecycle.onBeforeSave(values)
    }

    const mutation = isCreating ? createMutation : updateMutation

    if (!mutation) {
      toast({
        title: 'Error',
        description: 'Operation not available',
        variant: 'destructive'
      })
      return
    }

    const payload = isCreating
      ? processedData
      : { id: id!, content: processedData.content }

    mutation.mutate(payload, {
      onSuccess: (result) => {
        if (storageKey) {
          localStorage.removeItem(storageKey)
        }
        toast({ title: 'Saved successfully' })
        if (isCreating) {
          form.reset(values)
        } else {
          form.resetField('content', { defaultValue: values.content })
        }

        if (isCreating && config.lifecycle?.onCreateSuccess) {
          config.lifecycle.onCreateSuccess(result.id, result)
        } else if (config.lifecycle?.onAfterSave) {
          config.lifecycle.onAfterSave(result)
        }
      },
      onError: () => {
        toast({
          title: 'Save failed',
          description: 'Please try again',
          variant: 'destructive'
        })
      }
    })
  }, [canSave, config, isCreating, id, createMutation, updateMutation, storageKey, toast, form])

  // Keyboard shortcut: Ctrl+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        if (!canSave) {
          return
        }
        form.handleSubmit(handleSubmit)()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [canSave, form, handleSubmit])

  // Export PDF
  const handleExportPdf = async () => {
    if (!useExportPdf || !document || !id) return
    setIsExporting(true)
    try {
      await useExportPdf(id, document.title)
    } catch {
      toast({
        title: 'Export failed',
        description: 'Failed to export PDF',
        variant: 'destructive'
      })
    } finally {
      setIsExporting(false)
    }
  }

  // Loading state
  if (!isCreating && isLoading) {
    return <div className="p-8">Loading...</div>
  }

  if (!isCreating && !document) {
    return <div className="p-8">Document not found</div>
  }

  const displayTitle = isCreating ? 'New Document' : document?.title

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(returnPath)}>
            <ArrowLeft className="w-4 h-4" />
          </Button>

          <div className="flex items-center gap-2">
            {config.fields.title?.enabled ? (
          <Input
            {...form.register('title')}
            placeholder={config.fields.title.placeholder || 'Enter title...'}
            className="text-lg font-semibold border-transparent hover:border-slate-200 focus:border-indigo-500 w-[300px]"
            onBlur={handleTitleBlur}
          />
        ) : (
              <h1 className="text-lg font-semibold">{displayTitle}</h1>
            )}

            {document?.job_title && (
              <p className="text-sm text-slate-500">
                {document.company_name ? `${document.company_name} · ` : ''}
                {document.job_title}
              </p>
            )}
          </div>

          {config.ui?.showBusinessBadge && document && document.business_type !== 'resume' && (
            <Badge variant="outline" className="bg-indigo-50 text-indigo-700">
              {document.business_type === 'tailored_resume' ? 'Tailored Resume' : 'Cover Letter'}
            </Badge>
          )}

          {config.slots?.headerExtra}
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

          {config.slots?.actionsBefore}

          {config.ui?.showExportPdf && !isCreating && useExportPdf && (
            <Button variant="outline" onClick={handleExportPdf} disabled={isExporting}>
              {isExporting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Download className="w-4 h-4 mr-2" />
              )}
              Export PDF
            </Button>
          )}

          <Button
            onClick={form.handleSubmit(handleSubmit)}
            disabled={!canSave}
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save
          </Button>

          {config.slots?.actionsAfter}
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
          <div className="h-full overflow-auto bg-slate-50 p-8 flex justify-center items-start">
            <div className="bg-white shadow-sm border min-h-[297mm] w-[210mm]">
              <MarkdownPreview content={form.watch('content')} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export * from './types'
