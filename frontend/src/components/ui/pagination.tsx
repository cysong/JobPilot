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
  const startPage = Math.max(1, Math.min(currentPage - 2, totalPages - pagesToShow + 1))
  const endPage = Math.min(totalPages, startPage + pagesToShow - 1)
  const pageNumbers = Array.from(
    { length: endPage - startPage + 1 },
    (_, index) => startPage + index
  )

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
        {pageNumbers.map((pageNum) => {
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
        {endPage < totalPages && (
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
