import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Filter } from 'lucide-react'

import { useJobs } from '@/features/jobs/hooks/useJobs'
import type { JobFiltersRequest } from '@/types/job'
import { JobCard } from '@/features/jobs/components/JobCard'
import { JobFilters } from '@/features/jobs/components/JobFilters'
import { JobSearch } from '@/features/jobs/components/JobSearch'
import { JobPagination } from '@/features/jobs/components/JobPagination'
import { Button } from '@/components/ui/button'
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'

export default function JobListingPage() {
    const [searchParams] = useSearchParams()
    const [isMobileFiltersOpen, setIsMobileFiltersOpen] = useState(false)

    // Parse filters from URL
    const filters: JobFiltersRequest = {
        page: parseInt(searchParams.get('page') || '1'),
        page_size: 10,
        sort_by: searchParams.get('sort_by') || 'listed_at',
        sort_order: (searchParams.get('sort_order') as 'asc' | 'desc') || 'desc',
        keyword: searchParams.get('keyword') || undefined,
        location_cities: searchParams.getAll('location_cities'),
        work_types: searchParams.getAll('work_types'),
        companies: searchParams.getAll('companies'),
    }

    const { data, isLoading, isError } = useJobs(filters)

    // Scroll to top on page change
    useEffect(() => {
        window.scrollTo({ top: 0, behavior: 'smooth' })
    }, [filters.page])

    return (
        <div className="flex flex-col h-full">
            {/* Header / Search Bar */}
            <div className="bg-white border-b border-slate-200 sticky top-[65px] z-30">
                <div className="max-w-7xl mx-auto px-4 py-4">
                    <div className="flex items-center gap-4">
                        <div className="flex-1">
                            <JobSearch />
                        </div>

                        {/* Mobile Filter Toggle */}
                        <Sheet open={isMobileFiltersOpen} onOpenChange={setIsMobileFiltersOpen}>
                            <SheetTrigger asChild>
                                <Button variant="outline" size="icon" className="lg:hidden">
                                    <Filter className="h-4 w-4" />
                                </Button>
                            </SheetTrigger>
                            <SheetContent side="left" className="w-[300px] sm:w-[400px]">
                                <SheetHeader>
                                    <SheetTitle>Filters</SheetTitle>
                                </SheetHeader>
                                <div className="mt-6">
                                    <JobFilters />
                                </div>
                            </SheetContent>
                        </Sheet>
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-8 w-full">
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                    {/* Desktop Filters Sidebar */}
                    <div className="hidden lg:block lg:col-span-1">
                        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200 sticky top-40">
                            <JobFilters />
                        </div>
                    </div>

                    {/* Job List */}
                    <div className="lg:col-span-3 space-y-6">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-semibold text-slate-900">
                                {isLoading ? (
                                    <Skeleton className="h-8 w-32" />
                                ) : (
                                    `${data?.total || 0} Jobs Found`
                                )}
                            </h2>
                            {/* Add Sort Dropdown here later */}
                        </div>

                        {isLoading ? (
                            // Loading Skeletons
                            <div className="space-y-4">
                                {[1, 2, 3].map((i) => (
                                    <div key={i} className="bg-white p-4 rounded-lg border border-slate-200 space-y-3">
                                        <div className="flex justify-between">
                                            <div className="space-y-2">
                                                <Skeleton className="h-6 w-48" />
                                                <Skeleton className="h-4 w-32" />
                                            </div>
                                            <Skeleton className="h-12 w-12 rounded-md" />
                                        </div>
                                        <div className="flex gap-2">
                                            <Skeleton className="h-4 w-20" />
                                            <Skeleton className="h-4 w-20" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : isError ? (
                            <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                                <p className="text-red-500">Failed to load jobs. Please try again.</p>
                            </div>
                        ) : data?.items.length === 0 ? (
                            <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                                <p className="text-slate-500">No jobs found matching your criteria.</p>
                                <Button
                                    variant="link"
                                    onClick={() => window.location.href = '/jobs'}
                                    className="mt-2 text-indigo-600"
                                >
                                    Clear all filters
                                </Button>
                            </div>
                        ) : (
                            <>
                                <div className="space-y-4">
                                    {data?.items.map((job) => (
                                        <JobCard key={job.id} job={job} />
                                    ))}
                                </div>
                                <JobPagination
                                    currentPage={data?.page || 1}
                                    totalPages={data?.total_pages || 1}
                                />
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
