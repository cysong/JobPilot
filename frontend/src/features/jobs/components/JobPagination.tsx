import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'

interface JobPaginationProps {
    currentPage: number
    totalPages: number
}

export function JobPagination({ currentPage, totalPages }: JobPaginationProps) {
    const [searchParams, setSearchParams] = useSearchParams()

    const handlePageChange = (page: number) => {
        const newParams = new URLSearchParams(searchParams)
        newParams.set('page', page.toString())
        setSearchParams(newParams)
        window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    if (totalPages <= 1) return null

    return (
        <div className="flex items-center justify-center gap-2 mt-8">
            <Button
                variant="outline"
                size="icon"
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage <= 1}
                className="h-9 w-9"
            >
                <ChevronLeft className="h-4 w-4" />
                <span className="sr-only">Previous page</span>
            </Button>

            <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    // Simple logic to show a window of pages around current
                    let pageNum = i + 1
                    if (totalPages > 5) {
                        if (currentPage > 3) {
                            pageNum = currentPage - 3 + i
                        }
                        if (pageNum > totalPages) {
                            pageNum = totalPages - 4 + i
                        }
                    }

                    // Ensure we don't go out of bounds (simple clamp)
                    if (pageNum < 1) pageNum = i + 1

                    return (
                        <Button
                            key={pageNum}
                            variant={currentPage === pageNum ? "default" : "ghost"}
                            size="sm"
                            onClick={() => handlePageChange(pageNum)}
                            className={`h-9 w-9 ${currentPage === pageNum ? 'bg-indigo-600 hover:bg-indigo-700' : ''}`}
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
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage >= totalPages}
                className="h-9 w-9"
            >
                <ChevronRight className="h-4 w-4" />
                <span className="sr-only">Next page</span>
            </Button>
        </div>
    )
}
