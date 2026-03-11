import { useEffect, useState, type FormEvent } from 'react'
import { format } from 'date-fns'
import { Link, useSearchParams } from 'react-router-dom'
import {
    ExternalLink,
    RefreshCw,
    Building2,
    Calendar,
    Search,
    X,
} from 'lucide-react'

import { useApplications, useApplicationMutations } from '@/features/applications/hooks/useApplications'
import { ApplicationStatusBadge } from '@/features/applications/components/ApplicationStatusBadge'
import type { ApplicationStatus } from '@/types/application'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { JobPagination } from '@/features/jobs/components/JobPagination'

export default function ApplicationListingPage() {
    const [searchParams, setSearchParams] = useSearchParams()
    const currentPage = parseInt(searchParams.get('page') || '1')
    const pageSize = parseInt(searchParams.get('page_size') || '20')
    const keywordParam = searchParams.get('keyword') || ''
    const statusParam = (searchParams.get('status') as ApplicationStatus | null) || null
    const [keyword, setKeyword] = useState(keywordParam)

    const { data, isLoading, isError } = useApplications({
        page: currentPage,
        page_size: pageSize,
        keyword: keywordParam || undefined,
        status: statusParam || undefined,
    })
    const { retryCoverLetter } = useApplicationMutations()
    const hasActiveFilters = Boolean(keywordParam || statusParam)

    useEffect(() => {
        setKeyword(keywordParam)
    }, [keywordParam])

    const updateSearchParams = (next: { keyword?: string; status?: string | null; page?: number }) => {
        const newParams = new URLSearchParams(searchParams)
        const nextKeyword = next.keyword ?? keywordParam
        const nextStatus = next.status === undefined ? statusParam : next.status
        const nextPage = next.page ?? 1

        if (nextKeyword) {
            newParams.set('keyword', nextKeyword)
        } else {
            newParams.delete('keyword')
        }

        if (nextStatus) {
            newParams.set('status', nextStatus)
        } else {
            newParams.delete('status')
        }

        newParams.set('page', nextPage.toString())
        newParams.set('page_size', pageSize.toString())
        setSearchParams(newParams)
    }

    const handleSearch = (e: FormEvent) => {
        e.preventDefault()
        updateSearchParams({ keyword, page: 1 })
    }

    const handleClearSearch = () => {
        setKeyword('')
        updateSearchParams({ keyword: '', page: 1 })
    }

    const handleStatusChange = (value: string) => {
        updateSearchParams({ status: value === 'all' ? null : value, page: 1 })
    }

    if (isLoading) {
        return (
            <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
                <h1 className="text-2xl font-bold text-slate-900">My Applications</h1>
                <div className="grid gap-4">
                    {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-32 w-full" />
                    ))}
                </div>
            </div>
        )
    }

    if (isError) {
        return (
            <div className="max-w-5xl mx-auto px-6 py-8">
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                    <p className="text-red-500">Failed to load applications.</p>
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold text-slate-900">My Applications</h1>
            </div>

            <div className="bg-white rounded-lg border border-slate-200 p-4 flex flex-col gap-3 sm:flex-row sm:items-center">
                <form onSubmit={handleSearch} className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        type="text"
                        placeholder="Search by job title or company..."
                        className="pl-10 pr-10 h-10"
                        value={keyword}
                        onChange={(e) => setKeyword(e.target.value)}
                    />
                    {keyword && (
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 p-0"
                            onClick={handleClearSearch}
                        >
                            <X className="h-4 w-4 text-slate-400 hover:text-slate-600" />
                        </Button>
                    )}
                </form>
                <div className="w-full sm:w-56">
                    <Select value={statusParam || 'all'} onValueChange={handleStatusChange}>
                        <SelectTrigger>
                            <SelectValue placeholder="Filter by status" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Statuses</SelectItem>
                            <SelectItem value="Pending">Pending</SelectItem>
                            <SelectItem value="Tailoring">Tailoring</SelectItem>
                            <SelectItem value="Ready">Ready</SelectItem>
                            <SelectItem value="Applied">Applied</SelectItem>
                            <SelectItem value="PhoneScreen">Phone Screen</SelectItem>
                            <SelectItem value="Interviewing">Interviewing</SelectItem>
                            <SelectItem value="Offer">Offer</SelectItem>
                            <SelectItem value="Rejected">Rejected</SelectItem>
                            <SelectItem value="Failed">Failed</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                <Button onClick={() => updateSearchParams({ keyword: '', status: null, page: 1 })} variant="outline">
                    Reset
                </Button>
            </div>

            {data?.items.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                    {hasActiveFilters ? (
                        <>
                            <p className="text-slate-500">No applications match your current search/filter.</p>
                            <Button
                                variant="link"
                                className="mt-2 text-indigo-600"
                                onClick={() => updateSearchParams({ keyword: '', status: null, page: 1 })}
                            >
                                Clear filters
                            </Button>
                        </>
                    ) : (
                        <>
                            <p className="text-slate-500">You haven't applied to any jobs yet.</p>
                            <Button asChild variant="link" className="mt-2 text-indigo-600">
                                <Link to="/jobs">Browse Jobs</Link>
                            </Button>
                        </>
                    )}
                </div>
            ) : (
                <div className="grid gap-4">
                    {data?.items.map((app) => {
                        const company = app.job?.company_name || app.job?.advertiser_name || 'Unknown Company'
                        return (
                            <Card key={app.id} className="overflow-hidden">
                                <CardHeader className="bg-slate-50/50 border-b border-slate-100 py-4">
                                    <div className="flex justify-between items-start">
                                        <div className="space-y-1">
                                            <Link to={`/applications/${app.id}`}>
                                                <CardTitle className="text-lg font-semibold text-slate-900 hover:text-indigo-600 transition-colors cursor-pointer">
                                                    {app.job?.title || 'Unknown Job'}
                                                </CardTitle>
                                            </Link>
                                            <div className="flex items-center text-sm text-slate-500 gap-2">
                                                <Building2 className="h-4 w-4" />
                                                <span>{company}</span>
                                            </div>
                                        </div>
                                        <ApplicationStatusBadge status={app.status} />
                                    </div>
                                </CardHeader>
                                <CardContent className="py-4">
                                    <div className="flex items-center text-sm text-slate-500 gap-4">
                                        <div className="flex items-center gap-1.5">
                                            <Calendar className="h-4 w-4" />
                                            <span>Applied {format(new Date(app.created_at), 'MMM d, yyyy')}</span>
                                        </div>
                                        {app.last_error && (
                                            <span className="text-red-500 text-xs bg-red-50 px-2 py-1 rounded">
                                                Error: {app.last_error}
                                            </span>
                                        )}
                                    </div>
                                </CardContent>
                                <CardFooter className="bg-slate-50/50 border-t border-slate-100 py-3 flex gap-2 justify-end">
                                    <Button variant="outline" size="sm" asChild>
                                        <Link to={`/jobs/${app.job_id}`}>
                                            <ExternalLink className="h-3.5 w-3.5 mr-2" />
                                            View Job
                                        </Link>
                                    </Button>

                                    {app.status === 'Failed' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => retryCoverLetter.mutate({ id: app.id })}
                                            disabled={retryCoverLetter.isPending}
                                        >
                                            <RefreshCw className={`h-3.5 w-3.5 mr-2 ${retryCoverLetter.isPending ? 'animate-spin' : ''}`} />
                                            Retry
                                        </Button>
                                    )}
                                </CardFooter>
                            </Card>
                        )
                    })}
                </div>
            )}

            {!!data && data.total_pages > 1 && (
                <JobPagination currentPage={currentPage} totalPages={data.total_pages} />
            )}
        </div>
    )
}
