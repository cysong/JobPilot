import { format } from 'date-fns'
import { Link } from 'react-router-dom'
import {
    FileText,
    ExternalLink,
    Download,
    RefreshCw,
    Eye,
    Building2,
    Calendar
} from 'lucide-react'

import { useApplications, useApplicationMutations } from '@/features/applications/hooks/useApplications'
import { resumeApi } from '@/api/resumes'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/use-toast'

export default function ApplicationListingPage() {
    const { data, isLoading, isError } = useApplications()
    const { retryCoverLetter } = useApplicationMutations()
    const { toast } = useToast()

    const handleDownloadPdf = async (resumeId: string, title: string) => {
        try {
            const blob = await resumeApi.exportResume(resumeId)
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `${title.replace(/\s+/g, '_')}_Resume.pdf`
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
            document.body.removeChild(a)
        } catch (error) {
            toast({
                title: 'Error',
                description: 'Failed to download PDF',
                variant: 'destructive'
            })
        }
    }

    const getStatusBadge = (status: string) => {
        const normalized = status?.toLowerCase?.() || ''
        switch (normalized) {
            case 'pending':
                return <Badge variant="secondary">Pending</Badge>
            case 'tailoring':
                return <Badge variant="secondary" className="animate-pulse">Tailoring</Badge>
            case 'ready':
                return <Badge className="bg-green-500 hover:bg-green-600">Ready</Badge>
            case 'applied':
                return <Badge variant="outline">Applied</Badge>
            case 'phonescreen':
                return <Badge variant="outline">Phone Screen</Badge>
            case 'interviewing':
                return <Badge variant="outline">Interviewing</Badge>
            case 'offer':
                return <Badge className="bg-amber-400 text-slate-900 hover:bg-amber-500">Offer</Badge>
            case 'rejected':
                return <Badge variant="secondary">Rejected</Badge>
            case 'failed':
                return <Badge className="bg-red-500 text-white hover:bg-red-600">Failed</Badge>
            default:
                return <Badge variant="secondary">{status || 'Unknown'}</Badge>
        }
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

            {data?.items.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                    <p className="text-slate-500">You haven't applied to any jobs yet.</p>
                    <Button asChild variant="link" className="mt-2 text-indigo-600">
                        <Link to="/jobs">Browse Jobs</Link>
                    </Button>
                </div>
            ) : (
                <div className="grid gap-4">
                    {data?.items.map((app) => {
                        const status = app.status?.toLowerCase?.() || app.status
                        const company = app.job?.company_name || app.job?.advertiser_name || 'Unknown Company'
                        return (
                            <Card key={app.id} className="overflow-hidden">
                                <CardHeader className="bg-slate-50/50 border-b border-slate-100 py-4">
                                    <div className="flex justify-between items-start">
                                        <div className="space-y-1">
                                            <CardTitle className="text-lg font-semibold text-slate-900">
                                                {app.job?.title || 'Unknown Job'}
                                            </CardTitle>
                                            <div className="flex items-center text-sm text-slate-500 gap-2">
                                                <Building2 className="h-4 w-4" />
                                                <span>{company}</span>
                                            </div>
                                        </div>
                                        {getStatusBadge(status)}
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

                                    {status === 'ready' && (
                                        <>
                                            <Button variant="outline" size="sm" asChild>
                                                <Link to={`/resumes/${app.resume_id}`}>
                                                    <FileText className="h-3.5 w-3.5 mr-2" />
                                                    Edit Resume
                                                </Link>
                                            </Button>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleDownloadPdf(app.resume_id, app.job?.title || 'Resume')}
                                            >
                                                <Download className="h-3.5 w-3.5 mr-2" />
                                                PDF
                                            </Button>
                                        </>
                                    )}

                                    {status === 'failed' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => retryCoverLetter.mutate(app.id)}
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
        </div>
    )
}
