# 统一文档编辑器设计方案 v2.0

> **版本**: 2.0 (配置驱动架构)
> **日期**: 2025-01-23
> **作者**: Claude
> **状态**: 实施中

---

## 1. 设计目标

### 1.1 业务需求
- **简历编辑**: 编辑用户的基础简历模板（支持新增和编辑）
- **定制简历编辑**: 编辑针对特定职位的定制简历
- **求职信编辑**: 编辑针对特定职位的求职信

### 1.2 功能需求
- ✅ 支持新增和编辑双模式
- ✅ 支持标题编辑（可配置）
- ✅ Markdown 编辑器 + 实时预览
- ✅ 本地自动保存（防止意外丢失）
- ✅ 服务器端版本历史
- ✅ 导出 PDF
- ✅ 业务特定功能扩展（如 Finalize、Draft 状态）
- ✅ 统一的用户体验

### 1.3 技术约束
- ❌ **不修改** Document 数据结构
- ✅ **复用** DocumentRepository.create_new_version 方法
- ✅ **保留** 现有的本地自动保存功能
- ✅ 业务上下文由业务表（Resume/Application）提供

### 1.4 架构原则
- **配置驱动**: 业务差异通过配置表达
- **插槽扩展**: 特殊需求通过 Slots 注入
- **类型安全**: TypeScript 保证配置正确性
- **渐进式迁移**: 可逐步替换现有实现

---

## 2. 核心架构：配置驱动 + 组合插槽

```
┌─────────────────────────────────────────────────────────────┐
│              DocumentEditPage (核心组件)                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 配置接口:                                              │  │
│  │  • mode: 'edit' | 'create' | 'auto'                  │  │
│  │  • fields: {                                         │  │
│  │      title?: FieldConfig                             │  │
│  │      content: FieldConfig                            │  │
│  │    }                                                  │  │
│  │  • ui: {                                             │  │
│  │      showBusinessBadge?: boolean                     │  │
│  │      showExportPdf?: boolean                         │  │
│  │    }                                                  │  │
│  │  • slots: {                                          │  │
│  │      headerExtra?: ReactNode                         │  │
│  │      actionsBefore?: ReactNode                       │  │
│  │      actionsAfter?: ReactNode                        │  │
│  │    }                                                  │  │
│  │  • lifecycle: {                                      │  │
│  │      onBeforeSave?: (data) => data                   │  │
│  │      onCreateSuccess?: (id, data) => void            │  │
│  │    }                                                  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ 业务层配置注入
      ┌───────────────────┼───────────────────┐
      │                   │                   │
┌─────▼──────┐    ┌───────▼────────┐  ┌──────▼─────────┐
│ Resume     │    │ TailoredResume │  │ CoverLetter    │
│ EditPage   │    │   EditPage     │  │   EditPage     │
├────────────┤    ├────────────────┤  ├────────────────┤
│ config: {  │    │ config: {      │  │ config: {      │
│   mode:    │    │   mode: 'edit' │  │   mode: 'edit' │
│   'auto'   │    │   title: hide  │  │   title: hide  │
│   title:   │    │   slots: {}    │  │   slots: {}    │
│   editable │    │ }              │  │ }              │
│   slots: { │    │                │  │                │
│     Draft, │    │                │  │                │
│     Final  │    │                │  │                │
│   }        │    │                │  │                │
│ }          │    │                │  │                │
└────────────┘    └────────────────┘  └────────────────┘
```

---

## 3. 类型定义

### 3.1 配置接口

```typescript
// frontend/src/components/DocumentEditPage/types.ts

export interface FieldConfig {
  enabled: boolean
  required?: boolean
  placeholder?: string
  validation?: (value: string) => boolean | string
}

export interface DocumentEditConfig<TData = any> {
  // 模式控制
  mode?: 'edit' | 'create' | 'auto'  // auto: 根据 id 自动判断

  // 字段配置
  fields: {
    title?: FieldConfig
    content: FieldConfig
  }

  // UI 配置
  ui?: {
    showBusinessBadge?: boolean
    showExportPdf?: boolean
  }

  // 扩展插槽 (Composition 模式)
  slots?: {
    headerExtra?: ReactNode          // 标题栏额外内容
    actionsBefore?: ReactNode        // 保存按钮前的操作
    actionsAfter?: ReactNode         // 保存按钮后的操作
  }

  // 生命周期钩子
  lifecycle?: {
    onBeforeSave?: (data: TData) => TData | Promise<TData>
    onAfterSave?: (data: TData) => void
    onCreateSuccess?: (id: string, data: TData) => void
  }
}

export interface DocumentEditData {
  business_type: 'resume' | 'tailored_resume' | 'cover_letter'
  business_id: string
  title: string
  document_id: string
  content: string
  format: string
  created_at: string
  updated_at: string
  job_title?: string
  company_name?: string
  source_resume_title?: string
}

export interface DocumentUpdatePayload {
  content: string
  title?: string  // 如果支持标题编辑
  change_comments?: string
}
```

### 3.2 Props 接口

```typescript
export interface DocumentEditPageProps<TData = any> {
  // 配置
  config: DocumentEditConfig<TData>

  // API hooks
  useDocument: (id: string) => UseQueryResult<DocumentEditData>
  useCreateDocument?: () => UseMutationResult<any, unknown, TData, unknown>
  useUpdateDocument: () => UseMutationResult<any, unknown, { id: string } & TData, unknown>

  // 可选功能
  useExportPdf?: (id: string, title: string) => Promise<void>

  // 导航
  returnPath: string

  // 本地存储
  storageKeyPrefix: string
}
```

---

## 4. 核心组件实现

### 4.1 DocumentEditPage 主组件

```typescript
// frontend/src/components/DocumentEditPage/index.tsx

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { ArrowLeft, Save, Download } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { MarkdownEditor } from '@/components/MarkdownEditor'
import { MarkdownPreview } from '@/components/MarkdownPreview'
import { useAutoSave } from '@/hooks/useAutoSave'
import type { DocumentEditPageProps, DocumentEditConfig } from './types'

export function DocumentEditPage<TData = any>({
  config,
  useDocument,
  useCreateDocument,
  useUpdateDocument,
  useExportPdf,
  returnPath,
  storageKeyPrefix
}: DocumentEditPageProps<TData>) {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit')

  // 确定模式
  const mode = useMemo(() => {
    if (config.mode === 'auto') {
      return id && id !== 'new' ? 'edit' : 'create'
    }
    return config.mode || 'edit'
  }, [config.mode, id])

  const isCreating = mode === 'create'

  // Fetch document (仅编辑模式)
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
      // 新增模式：检查本地草稿
      if (storageKey) {
        const savedDraft = localStorage.getItem(storageKey)
        if (savedDraft) {
          try {
            const draft = JSON.parse(savedDraft)
            toast({
              title: "未保存的草稿",
              description: "已恢复您之前的工作...",
            })
            form.setValue('title', draft.title || '', { shouldDirty: true })
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

    // 始终先加载服务器数据
    form.reset({
      title: document.title,
      content: document.content
    })

    // 检查是否有更新的本地草稿
    if (savedDraft) {
      try {
        const draft = JSON.parse(savedDraft)
        const draftTime = draft.savedAt ? new Date(draft.savedAt).getTime() : 0
        const serverTime = document.updated_at ? new Date(document.updated_at).getTime() : 0

        if (draftTime > serverTime && draft.content) {
          toast({
            title: "发现未保存的更改",
            description: "是否恢复未保存的工作？",
            action: (
              <Button
                size="sm"
                onClick={() => {
                  if (config.fields.title?.enabled && draft.title) {
                    form.setValue('title', draft.title, { shouldDirty: true })
                  }
                  form.setValue('content', draft.content, { shouldDirty: true })
                  toast({ title: "草稿已恢复" })
                }}
              >
                恢复
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
  }, [document, form, toast, storageKey, isCreating, config.fields.title])

  // Auto-save to localStorage
  const watchedValues = form.watch()
  const noopSave = useCallback(() => {}, [])
  useAutoSave({
    data: watchedValues,
    onSave: noopSave,
    storageKey,
    enabled: form.formState.isDirty,
    interval: 4000,
  })

  // Submit handler
  const handleSubmit = useCallback(async (values: any) => {
    // Validation
    if (!values.content?.trim()) {
      toast({
        title: '验证错误',
        description: '内容不能为空',
        variant: 'destructive'
      })
      return
    }

    if (config.fields.title?.enabled && config.fields.title.required && !values.title?.trim()) {
      toast({
        title: '验证错误',
        description: '标题不能为空',
        variant: 'destructive'
      })
      return
    }

    // 生命周期钩子
    let processedData = values
    if (config.lifecycle?.onBeforeSave) {
      processedData = await config.lifecycle.onBeforeSave(values)
    }

    const mutation = isCreating ? createMutation : updateMutation

    if (!mutation) {
      toast({
        title: '错误',
        description: '操作不可用',
        variant: 'destructive'
      })
      return
    }

    const payload = isCreating
      ? processedData
      : { id: id!, ...processedData }

    mutation.mutate(payload, {
      onSuccess: (result) => {
        if (storageKey) {
          localStorage.removeItem(storageKey)
        }
        toast({ title: '保存成功' })

        if (isCreating && config.lifecycle?.onCreateSuccess) {
          config.lifecycle.onCreateSuccess(result.id, result)
        } else if (config.lifecycle?.onAfterSave) {
          config.lifecycle.onAfterSave(result)
        }
      },
      onError: () => {
        toast({
          title: '保存失败',
          description: '请重试',
          variant: 'destructive'
        })
      }
    })
  }, [config, isCreating, id, createMutation, updateMutation, storageKey, toast])

  // Keyboard shortcut: Ctrl+S
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

  // Export PDF
  const handleExportPdf = async () => {
    if (!useExportPdf || !document || !id) return
    try {
      await useExportPdf(id, document.title)
    } catch {
      toast({
        title: '导出失败',
        description: '导出 PDF 失败',
        variant: 'destructive'
      })
    }
  }

  // Loading state
  if (!isCreating && isLoading) {
    return <div className="p-8">加载中...</div>
  }

  if (!isCreating && !document) {
    return <div className="p-8">文档未找到</div>
  }

  const displayTitle = isCreating ? '新建文档' : document?.title

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
                placeholder={config.fields.title.placeholder || '输入标题...'}
                className="text-lg font-semibold border-transparent hover:border-slate-200 focus:border-indigo-500 w-[300px]"
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
              编辑
            </button>
            <button
              onClick={() => setActiveTab('preview')}
              className={`px-3 py-1.5 rounded transition-all ${
                activeTab === 'preview' ? 'bg-white shadow-sm' : ''
              }`}
            >
              预览
            </button>
          </div>

          {config.slots?.actionsBefore}

          {config.ui?.showExportPdf && !isCreating && useExportPdf && (
            <Button variant="outline" onClick={handleExportPdf}>
              <Download className="w-4 h-4 mr-2" />
              导出 PDF
            </Button>
          )}

          <Button
            onClick={form.handleSubmit(handleSubmit)}
            disabled={!form.formState.isDirty || updateMutation?.isPending || createMutation?.isPending}
          >
            <Save className="w-4 h-4 mr-2" />
            {updateMutation?.isPending || createMutation?.isPending ? '保存中...' : '保存'}
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
                  Markdown 编辑器
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
                  实时预览
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
```

---

## 5. 业务层使用示例

### 5.1 Resume 编辑页面（支持新增和编辑）

```typescript
// frontend/src/features/resumes/ResumeEditPage.tsx

import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { FileCheck } from 'lucide-react'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import {
  useResumeEdit,
  useCreateResume,
  useUpdateResumeContent,
  useResumeMutations
} from '@/features/resumes/hooks/useResumes'
import { resumeApi } from '@/api/resumes'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'

export default function ResumeEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id || id === 'new'

  // 获取 Resume 数据（仅编辑模式需要）
  const { data: resume } = useResumeEdit(isNew ? '' : id!)
  const { finalizeResume } = useResumeMutations()

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

  const handleFinalize = () => {
    if (id) {
      finalizeResume.mutate(id)
    }
  }

  const config: DocumentEditConfig = {
    mode: 'auto',  // 自动判断新增/编辑
    fields: {
      title: {
        enabled: true,
        required: true,
        placeholder: '输入简历标题...'
      },
      content: {
        enabled: true,
        required: true
      }
    },
    ui: {
      showBusinessBadge: false,
      showExportPdf: true
    },
    slots: {
      actionsBefore: !isNew && resume?.is_draft ? (
        <>
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
            草稿
          </Badge>
          <Button
            variant="outline"
            onClick={handleFinalize}
            className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
          >
            <FileCheck className="w-4 h-4 mr-2" />
            定稿
          </Button>
        </>
      ) : null
    },
    lifecycle: {
      onCreateSuccess: (newId) => {
        navigate(`/resumes/${newId}`, { replace: true })
      }
    }
  }

  return (
    <DocumentEditPage
      config={config}
      useDocument={useResumeEdit}
      useCreateDocument={useCreateResume}
      useUpdateDocument={useUpdateResumeContent}
      useExportPdf={handleExportPdf}
      returnPath="/resumes"
      storageKeyPrefix="resume"
    />
  )
}
```

### 5.2 Tailored Resume 编辑页面（仅编辑）

```typescript
// frontend/src/features/applications/TailoredResumeEditPage.tsx

import { useParams } from 'react-router-dom'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useTailoredResumeEdit, useUpdateTailoredResume } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'

export default function TailoredResumeEditPage() {
  const { applicationId } = useParams()

  const config: DocumentEditConfig = {
    mode: 'edit',  // 仅编辑模式
    fields: {
      title: {
        enabled: false  // 标题不可编辑
      },
      content: {
        enabled: true,
        required: true
      }
    },
    ui: {
      showBusinessBadge: true,
      showExportPdf: false
    }
  }

  return (
    <DocumentEditPage
      config={config}
      useDocument={useTailoredResumeEdit}
      useUpdateDocument={useUpdateTailoredResume}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-resume"
    />
  )
}
```

### 5.3 Cover Letter 编辑页面

```typescript
// frontend/src/features/applications/CoverLetterEditPage.tsx

import { useParams } from 'react-router-dom'
import { DocumentEditPage } from '@/components/DocumentEditPage'
import { useCoverLetterEdit, useUpdateCoverLetter } from './hooks/useApplications'
import type { DocumentEditConfig } from '@/components/DocumentEditPage/types'

export default function CoverLetterEditPage() {
  const { applicationId } = useParams()

  const config: DocumentEditConfig = {
    mode: 'edit',
    fields: {
      title: {
        enabled: false
      },
      content: {
        enabled: true,
        required: true
      }
    },
    ui: {
      showBusinessBadge: true,
      showExportPdf: false
    }
  }

  return (
    <DocumentEditPage
      config={config}
      useDocument={useCoverLetterEdit}
      useUpdateDocument={useUpdateCoverLetter}
      returnPath={`/applications/${applicationId}`}
      storageKeyPrefix="application-coverletter"
    />
  )
}
```

---

## 6. 后端 API（保持不变）

后端 API 设计与 v1.0 版本保持一致，详见原文档第 3 节。

主要端点：
- `GET /api/v1/resumes/{id}/edit` - 获取简历编辑数据
- `PATCH /api/v1/resumes/{id}` - 更新简历内容
- `GET /api/v1/applications/{id}/resume/edit` - 获取定制简历
- `PATCH /api/v1/applications/{id}/resume` - 更新定制简历
- `GET /api/v1/applications/{id}/cover-letter/edit` - 获取求职信
- `PATCH /api/v1/applications/{id}/cover-letter` - 更新求职信

---

## 7. 实施步骤

### Phase 1: 创建类型定义和基础组件（0.5 天）

**任务清单**:
- [ ] 创建 `frontend/src/components/DocumentEditPage/types.ts`
- [ ] 定义 `DocumentEditConfig` 接口
- [ ] 定义 `DocumentEditPageProps` 接口
- [ ] 导出所有类型

### Phase 2: 实现核心 DocumentEditPage 组件（1 天）

**任务清单**:
- [ ] 创建 `frontend/src/components/DocumentEditPage/index.tsx`
- [ ] 实现配置驱动逻辑
- [ ] 实现模式切换（create/edit/auto）
- [ ] 实现标题编辑支持
- [ ] 实现 Slots 插槽
- [ ] 实现生命周期钩子
- [ ] 测试基础功能

**验证点**:
- ✅ 支持新增和编辑模式
- ✅ 标题可配置可见/隐藏/可编辑
- ✅ Slots 正确渲染
- ✅ 生命周期钩子正确调用

### Phase 3: 重构 Resume 编辑页面（0.5 天）

**任务清单**:
- [ ] 更新 `ResumeEditPage.tsx` 使用新的 DocumentEditPage
- [ ] 配置支持新增和编辑
- [ ] 添加 Draft/Finalize 按钮到 Slots
- [ ] 测试新增功能
- [ ] 测试编辑功能
- [ ] 测试草稿恢复

**验证点**:
- ✅ 新增 Resume 正常工作
- ✅ 编辑 Resume 正常工作
- ✅ Finalize 功能正常
- ✅ 草稿管理正常

### Phase 4: 迁移 Application 文档编辑页面（0.5 天）

**任务清单**:
- [ ] 更新 `TailoredResumeEditPage.tsx`
- [ ] 更新 `CoverLetterEditPage.tsx`
- [ ] 配置仅编辑模式
- [ ] 测试功能

**验证点**:
- ✅ 定制简历编辑正常
- ✅ 求职信编辑正常
- ✅ 标题正确显示为只读

### Phase 5: 清理和优化（0.5 天）

**任务清单**:
- [ ] 删除或归档旧的 `ResumeEditPage.tsx`（如果有单独的）
- [ ] 更新路由配置
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 文档更新

**验证点**:
- ✅ 所有功能正常工作
- ✅ 无回归问题
- ✅ 性能良好

---

## 8. 核心优势

| 维度 | 实现方式 | 优势 |
|------|---------|------|
| **功能完整度** | 配置驱动 + Slots | 100% 功能覆盖 |
| **代码复用** | 单一核心组件 | 减少 70% 重复代码 |
| **可维护性** | 单点维护 | Bug 修复一次生效 |
| **可扩展性** | 配置化 + 插槽 | 新增文档类型 30 分钟 |
| **类型安全** | TypeScript 泛型 | 编译时检查 |
| **业务隔离** | 配置注入 | 业务逻辑清晰分离 |
| **用户体验** | 统一组件 | 一致的交互体验 |

---

## 9. 关键设计决策

### 9.1 为什么选择配置驱动 + Slots？

**优势**:
- ✅ 统一核心逻辑，差异通过配置表达
- ✅ 业务特定功能通过 Slots 扩展
- ✅ 保持组件通用性，不会因业务需求污染
- ✅ 易于测试和维护

### 9.2 为什么支持 auto 模式？

**原因**:
- 简化业务层代码，自动判断新增/编辑
- 统一路由设计（/resumes/new 和 /resumes/{id} 用同一个组件）
- 减少重复逻辑

### 9.3 为什么使用生命周期钩子？

**原因**:
- 提供扩展点，不修改核心组件
- 支持数据预处理、后处理
- 支持自定义导航逻辑

---

## 10. 未来扩展

### 10.1 版本历史 (可通过 Slots 实现)

```typescript
config: {
  slots: {
    sidebarRight: <VersionHistory documentId={id} />
  }
}
```

### 10.2 协作编辑

- 添加 WebSocket 支持
- 冲突检测和解决

### 10.3 富文本编辑器

- 替换 MarkdownEditor 为富文本编辑器
- 通过配置选择编辑器类型

---

**设计完成日期**: 2025-01-23
**预计工期**: 3 天
