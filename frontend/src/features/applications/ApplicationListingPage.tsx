import { useEffect, useRef, useState, type FormEvent } from 'react'
import { formatDistanceToNow } from 'date-fns'
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
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { JobPagination } from '@/features/jobs/components/JobPagination'

type ListPositionState = {
    anchorApplicationId: string
    scrollY: number
    updatedAt: number
}

type ApplicationOrderState = {
    applicationIds: string[]
    updatedAt: number
}

const APPLICATION_LIST_POSITIONS_KEY = 'applications:list:positions'
const APPLICATION_LIST_RETURN_INTENT_KEY = 'applications:list:return-intent'
const APPLICATION_LIST_ORDERS_KEY = 'applications:list:orders'
const RESTORE_HIGHLIGHT_MS = 2000

const normalizeSearchParams = (params: URLSearchParams): string => {
    const entries = Array.from(params.entries()).sort(([aKey, aVal], [bKey, bVal]) => {
        if (aKey === bKey) return aVal.localeCompare(bVal)
        return aKey.localeCompare(bKey)
    })
    return entries
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
        .join('&')
}

const getContextKey = (params: URLSearchParams): string => {
    return `applications:list:${normalizeSearchParams(params)}`
}

const readPositions = (): Record<string, ListPositionState> => {
    try {
        const raw = sessionStorage.getItem(APPLICATION_LIST_POSITIONS_KEY)
        return raw ? (JSON.parse(raw) as Record<string, ListPositionState>) : {}
    } catch {
        return {}
    }
}

const writePositions = (positions: Record<string, ListPositionState>) => {
    sessionStorage.setItem(APPLICATION_LIST_POSITIONS_KEY, JSON.stringify(positions))
}

const readOrders = (): Record<string, ApplicationOrderState> => {
    try {
        const raw = sessionStorage.getItem(APPLICATION_LIST_ORDERS_KEY)
        return raw ? (JSON.parse(raw) as Record<string, ApplicationOrderState>) : {}
    } catch {
        return {}
    }
}

const writeOrders = (orders: Record<string, ApplicationOrderState>) => {
    sessionStorage.setItem(APPLICATION_LIST_ORDERS_KEY, JSON.stringify(orders))
}

export default function ApplicationListingPage() {
    const [searchParams, setSearchParams] = useSearchParams()
    const [highlightedApplicationId, setHighlightedApplicationId] = useState<string | null>(null)
    const previousContextKey = useRef<string | null>(null)
    const currentPage = parseInt(searchParams.get('page') || '1')
    const pageSize = parseInt(searchParams.get('page_size') || '20')
    const keywordParam = searchParams.get('keyword') || ''
    const statusParam = (searchParams.get('status') as ApplicationStatus | null) || null
    const contextKey = getContextKey(searchParams)
    const [keyword, setKeyword] = useState(keywordParam)

    const { data, isLoading, isFetching, isError } = useApplications({
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

    const handleOpenApplication = (applicationId: string) => {
        const positions = readPositions()
        positions[contextKey] = {
            anchorApplicationId: applicationId,
            scrollY: window.scrollY,
            updatedAt: Date.now(),
        }
        writePositions(positions)
    }

    useEffect(() => {
        if (previousContextKey.current && previousContextKey.current !== contextKey) {
            window.scrollTo({ top: 0, behavior: 'auto' })
        }
        previousContextKey.current = contextKey
    }, [contextKey])

    useEffect(() => {
        if (isLoading || isError) return

        const rawIntent = sessionStorage.getItem(APPLICATION_LIST_RETURN_INTENT_KEY)
        if (!rawIntent) return

        let intent: { contextKey: string; applicationId: string } | null = null
        try {
            intent = JSON.parse(rawIntent) as { contextKey: string; applicationId: string }
        } catch {
            sessionStorage.removeItem(APPLICATION_LIST_RETURN_INTENT_KEY)
            return
        }

        if (!intent || intent.contextKey !== contextKey) {
            return
        }

        sessionStorage.removeItem(APPLICATION_LIST_RETURN_INTENT_KEY)

        const positions = readPositions()
        const position = positions[contextKey]
        const targetApplicationId = intent.applicationId || position?.anchorApplicationId
        if (!targetApplicationId) return

        requestAnimationFrame(() => {
            const anchorElement = document.querySelector(`[data-application-id="${targetApplicationId}"]`)
            if (anchorElement instanceof HTMLElement) {
                anchorElement.scrollIntoView({ block: 'center', behavior: 'auto' })
            } else if (position?.scrollY !== undefined) {
                window.scrollTo({ top: position.scrollY, behavior: 'auto' })
            }
            setHighlightedApplicationId(targetApplicationId)
            window.setTimeout(() => setHighlightedApplicationId(null), RESTORE_HIGHLIGHT_MS)
        })
    }, [contextKey, isError, isLoading])

    useEffect(() => {
        if (isLoading || isError || !data) return

        const orders = readOrders()
        orders[contextKey] = {
            applicationIds: data.items.map((item) => item.id),
            updatedAt: Date.now(),
        }
        writeOrders(orders)
    }, [contextKey, data, isError, isLoading])

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

            <div className="text-sm font-medium text-slate-700">
                {data?.total ?? 0} Applications Found
            </div>

            {isError && !data ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                    <p className="text-red-500">Failed to load applications.</p>
                </div>
            ) : isLoading && !data ? (
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
                <div className="relative">
                    {isFetching && (
                        <div className="absolute inset-0 z-10 bg-white/65 backdrop-blur-[1px] rounded-lg border border-slate-100 p-4 space-y-3">
                            {[1, 2, 3].map((i) => (
                                <Skeleton key={i} className="h-20 w-full" />
                            ))}
                        </div>
                    )}
                    <div className="grid gap-4">
                    {data?.items.map((app) => {
                        const company = app.job?.company_name || app.job?.advertiser_name || 'Unknown Company'
                        const query = searchParams.toString()
                        const detailUrl = query ? `/applications/${app.id}?${query}` : `/applications/${app.id}`
                        return (
                            <Card
                                key={app.id}
                                data-application-id={app.id}
                                className={`overflow-hidden ${
                                    highlightedApplicationId === app.id ? 'ring-2 ring-amber-300 border-amber-300' : ''
                                }`}
                            >
                                <CardHeader className="bg-slate-50/50 border-b border-slate-100 py-4">
                                    <div className="flex justify-between items-start">
                                        <div className="space-y-1">
                                            <div className="flex items-center gap-2">
                                                <Link to={detailUrl} onClick={() => handleOpenApplication(app.id)}>
                                                    <CardTitle className="text-lg font-semibold text-slate-900 hover:text-indigo-600 transition-colors cursor-pointer">
                                                        {app.job?.title || 'Unknown Job'}
                                                    </CardTitle>
                                                </Link>
                                                {app.job?.is_expired && (
                                                    <TooltipProvider>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Badge className="bg-red-500 text-white hover:bg-red-600">Expired</Badge>
                                                            </TooltipTrigger>
                                                            <TooltipContent>
                                                                Posting marked as closed on source site.
                                                            </TooltipContent>
                                                        </Tooltip>
                                                    </TooltipProvider>
                                                )}
                                            </div>
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
                                            <span>Added {formatDistanceToNow(new Date(app.created_at), { addSuffix: true })}</span>
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
                </div>
            )}

            {!!data && data.total_pages > 1 && (
                <JobPagination currentPage={currentPage} totalPages={data.total_pages} />
            )}
        </div>
    )
}
