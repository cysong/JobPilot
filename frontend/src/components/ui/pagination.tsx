import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'

import { cn } from '@/utils/cn'
import { Button } from '@/components/ui/button'

interface PaginationProps {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  className?: string
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  className,
}: PaginationProps) {
  if (totalPages <= 1) return null

  const pagesToShow = Math.min(5, totalPages)

  return (
    <div className={cn('flex items-center justify-center gap-2', className)}>
      <Button
        variant="outline"
        size="icon"
        onClick={() => onPageChange(1)}
        disabled={currentPage <= 1}
        className="h-9 w-9"
      >
        <ChevronsLeft className="h-4 w-4" />
        <span className="sr-only">First page</span>
      </Button>

      <Button
        variant="outline"
        size="icon"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        className="h-9 w-9"
      >
        <ChevronLeft className="h-4 w-4" />
        <span className="sr-only">Previous page</span>
      </Button>

      <div className="flex items-center gap-1">
        {Array.from({ length: pagesToShow }, (_, i) => {
          let pageNum = i + 1
          if (totalPages > 5) {
            if (currentPage > 3) {
              pageNum = currentPage - 3 + i
            }
            if (pageNum > totalPages) {
              pageNum = totalPages - 4 + i
            }
          }

          if (pageNum < 1) pageNum = i + 1

          return (
            <Button
              key={pageNum}
              variant={currentPage === pageNum ? 'default' : 'ghost'}
              size="sm"
              onClick={() => onPageChange(pageNum)}
              className={cn(
                'h-9 w-9',
                currentPage === pageNum && 'bg-indigo-600 hover:bg-indigo-700'
              )}
            >
              {pageNum}
            </Button>
          )
        })}
        {totalPages > 5 && currentPage < totalPages - 2 && (
          <span className="text-slate-400 px-1">...</span>
        )}
      </div>

      <Button
        variant="outline"
        size="icon"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className="h-9 w-9"
      >
        <ChevronRight className="h-4 w-4" />
        <span className="sr-only">Next page</span>
      </Button>

      <Button
        variant="outline"
        size="icon"
        onClick={() => onPageChange(totalPages)}
        disabled={currentPage >= totalPages}
        className="h-9 w-9"
      >
        <ChevronsRight className="h-4 w-4" />
        <span className="sr-only">Last page</span>
      </Button>
    </div>
  )
}
