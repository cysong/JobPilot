import { MarkdownPreview } from '@/components/MarkdownPreview'
import type { MarkdownPreviewVariant } from '@/components/MarkdownPreview/variant'
import { cn } from '@/utils/cn'

interface MarkdownViewerProps {
  content: string
  className?: string
  viewportClassName?: string
  pageClassName?: string
  variant?: MarkdownPreviewVariant
}

export function MarkdownViewer({
  content,
  className,
  viewportClassName,
  pageClassName,
  variant,
}: MarkdownViewerProps) {
  return (
    <div className={cn('rounded-xl border border-slate-200 bg-slate-50', className)}>
      <div className={cn('overflow-auto p-4 sm:p-6', viewportClassName)}>
        <div
          className={cn(
            'mx-auto min-h-[297mm] w-full max-w-[210mm] bg-white shadow-sm ring-1 ring-slate-200',
            pageClassName,
          )}
        >
          <MarkdownPreview content={content} variant={variant} />
        </div>
      </div>
    </div>
  )
}
