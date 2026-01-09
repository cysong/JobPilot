import { useSearchParams } from 'react-router-dom'

import { Pagination } from '@/components/ui/pagination'

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

    return (
        <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={handlePageChange}
            className="mt-8"
        />
    )
}
