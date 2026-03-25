import { useMemo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { Link } from 'react-router-dom'
import {
    ExternalLink,
    RefreshCw,
    Calendar,
    Search,
    X,
} from 'lucide-react'

import { useApplications, useApplicationMutations } from '@/features/applications/hooks/useApplications'
import { ApplicationResolutionBadge } from '@/features/applications/components/ApplicationResolutionBadge'
import { ApplicationStatusBadge } from '@/features/applications/components/ApplicationStatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import {
    Select,
    SelectContent,
    SelectSeparator,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { JobPagination } from '@/features/jobs/components/JobPagination'
import {
  JobAttributeList,
  JobSourceCompanyLine,
} from '@/components/job/jobDisplay'
import { useApplicationListState } from '@/features/applications/hooks/useApplicationListState'
import { useApplicationListReturnRestore } from '@/features/applications/hooks/useApplicationListReturnRestore'

export default function ApplicationListingPage() {
    const {
        searchParams,
        currentPage,
        pageSize,
        keywordParam,
        statusParam,
        statusGroupParam,
        resolutionParam,
        contextKey,
        keyword,
        setKeyword,
        isSearchParamsReady,
        handleSearch,
        handleClearSearch,
        handleStatusChange,
        handleResolutionChange,
        handleReset,
        updateSearchParams,
    } = useApplicationListState()

    const { data, isLoading, isFetching, isError } = useApplications({
        page: currentPage,
        page_size: pageSize,
        keyword: keywordParam || undefined,
        status: statusParam || undefined,
        status_group: statusGroupParam || undefined,
        resolution: resolutionParam || 'ACTIVE',
    }, isSearchParamsReady)
    const { retryCoverLetter } = useApplicationMutations()
    const hasActiveFilters = Boolean(keywordParam || statusParam || statusGroupParam || resolutionParam)
    const isListLoading = !isSearchParamsReady || isLoading
    const visibleApplicationIds = useMemo(
        () => (data?.items || []).map((item) => item.id),
        [data],
    )
    const { highlightedApplicationId, handleOpenApplication } = useApplicationListReturnRestore({
        contextKey,
        isSearchParamsReady,
        isLoading,
        isError,
        itemIds: visibleApplicationIds,
    })

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
                    <Select value={statusGroupParam || statusParam || 'all'} onValueChange={handleStatusChange}>
                        <SelectTrigger>
                            <SelectValue placeholder="Filter by status" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Statuses</SelectItem>
                            <SelectItem value="in_progress">In Progress</SelectItem>
                            <SelectSeparator />
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
                <div className="w-full sm:w-56">
                    <Select value={resolutionParam || 'ACTIVE'} onValueChange={handleResolutionChange}>
                        <SelectTrigger>
                            <SelectValue placeholder="Filter by queue" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="ACTIVE">Active Queue</SelectItem>
                            <SelectItem value="JOB_CLOSED">Job Closed</SelectItem>
                            <SelectItem value="USER_SKIPPED">Skipped</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                <Button onClick={handleReset} variant="outline">
                    Reset
                </Button>
            </div>

            <div className="flex items-center gap-3 text-sm font-medium text-slate-700">
                <span>{data?.total ?? 0} Applications Found</span>
                {isSearchParamsReady && isFetching && !!data && (
                    <span className="inline-flex items-center gap-1.5 text-slate-500" aria-live="polite">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        <span>Updating results...</span>
                    </span>
                )}
            </div>

            {isError && !data ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                    <p className="text-red-500">Failed to load applications.</p>
                </div>
            ) : isListLoading && !data ? (
                <div className="grid gap-4">
                    {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-32 w-full" />
                    ))}
                </div>
            ) : data?.items.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                    {hasActiveFilters ? (
                        <>
                            <p className="text-slate-500">No applications match your current search/filter.</p>
                            <Button
                                variant="link"
                                className="mt-2 text-indigo-600"
                                onClick={() => updateSearchParams({ keyword: '', status: null, statusGroup: null, resolution: null, page: 1 })}
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
                <div className={`grid gap-4 transition-opacity ${isSearchParamsReady && isFetching ? 'opacity-60' : 'opacity-100'}`}>
                    {data?.items.map((app) => {
                        const query = searchParams.toString()
                        const detailUrl = query ? `/applications/${app.id}?${query}` : `/applications/${app.id}`
                        return (
                            <Card
                                key={app.id}
                                data-application-id={app.id}
                                className={`overflow-hidden bg-slate-50/50 ${
                                    highlightedApplicationId === app.id ? 'ring-2 ring-amber-300 border-amber-300' : ''
                                }`}
                            >
                                <CardContent className="space-y-4 p-5">
                                    <div className="flex justify-between items-start">
                                        <div className="space-y-1.5">
                                            <div className="flex items-center gap-2">
                                                <Link to={detailUrl} onClick={() => handleOpenApplication(app.id)}>
                                                    <CardTitle className="text-lg font-semibold text-slate-900 hover:text-indigo-600 transition-colors cursor-pointer">
                                                        {app.job?.title || 'Unknown Job'}
                                                    </CardTitle>
                                                </Link>
                                                {app.resolution !== 'ACTIVE' && (
                                                    <ApplicationResolutionBadge resolution={app.resolution} />
                                                )}
                                            </div>
                                            <JobSourceCompanyLine
                                                source={app.job?.source}
                                                companyName={app.job?.company_name}
                                                advertiserName={app.job?.advertiser_name}
                                                className="text-base"
                                                iconClassName="h-4 w-4"
                                            />
                                        </div>
                                        <div className="flex flex-col items-end gap-2">
                                            <ApplicationStatusBadge status={app.status} />
                                        </div>
                                    </div>

                                    <JobAttributeList
                                        job={app.job ?? {}}
                                        className="text-sm text-slate-500"
                                    />

                                    <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                                        <div className="flex items-center gap-1.5 text-sm text-slate-500">
                                            <Calendar className="h-4 w-4" />
                                            <span>Added {formatDistanceToNow(new Date(app.created_at), { addSuffix: true })}</span>
                                        </div>
                                        <div className="flex flex-wrap items-center justify-end gap-2">
                                            {app.last_error && (
                                                <span className="text-red-500 text-xs bg-red-50 px-2 py-1 rounded">
                                                Error: {app.last_error}
                                                </span>
                                            )}
                                            {app.status === 'Failed' && app.resolution === 'ACTIVE' && (
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
                                            <Button variant="outline" size="sm" asChild>
                                                <Link to={`/jobs/${app.job_id}`}>
                                                    <ExternalLink className="h-3.5 w-3.5 mr-2" />
                                                    View Job
                                                </Link>
                                            </Button>
                                        </div>
                                    </div>
                                </CardContent>
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
