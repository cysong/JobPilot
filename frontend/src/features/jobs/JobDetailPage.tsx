import { useParams, Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import {
    Building2,
    MapPin,
    Clock,
    DollarSign,
    ArrowLeft,
    Share2,
    ExternalLink
} from 'lucide-react'

import { useJobDetail } from '@/features/jobs/hooks/useJobs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export default function JobDetailPage() {
    const { jobId } = useParams()
    const { data: job, isLoading, isError } = useJobDetail(parseInt(jobId || '0'))

    if (isLoading) {
        return (
            <div className="min-h-screen bg-slate-50 p-4">
                <div className="max-w-4xl mx-auto space-y-6">
                    <Skeleton className="h-8 w-32" />
                    <div className="bg-white p-8 rounded-xl border border-slate-200 space-y-6">
                        <div className="space-y-4">
                            <Skeleton className="h-10 w-3/4" />
                            <div className="flex gap-4">
                                <Skeleton className="h-5 w-32" />
                                <Skeleton className="h-5 w-32" />
                            </div>
                        </div>
                        <Separator />
                        <div className="space-y-4">
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-2/3" />
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    if (isError || !job) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
                <Alert variant="destructive" className="max-w-md">
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>
                        Failed to load job details. The job may have expired or been removed.
                    </AlertDescription>
                    <Button asChild variant="outline" className="mt-4 w-full">
                        <Link to="/jobs">Back to Jobs</Link>
                    </Button>
                </Alert>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-12">
            {/* Header Navigation */}
            <div className="bg-white border-b border-slate-200 sticky top-0 z-20">
                <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
                    <Button variant="ghost" size="sm" asChild className="-ml-2 text-slate-600">
                        <Link to="/jobs">
                            <ArrowLeft className="h-4 w-4 mr-2" />
                            Back to Search
                        </Link>
                    </Button>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm">
                            <Share2 className="h-4 w-4 mr-2" />
                            Share
                        </Button>
                        <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700">
                            Apply Now
                            <ExternalLink className="h-4 w-4 ml-2" />
                        </Button>
                    </div>
                </div>
            </div>

            <main className="max-w-5xl mx-auto px-4 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Main Content */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Job Header Card */}
                        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                            <div className="flex justify-between items-start gap-4">
                                <div>
                                    <h1 className="text-2xl font-bold text-slate-900 mb-2">
                                        {job.title}
                                    </h1>
                                    <div className="flex items-center gap-2 text-slate-600 mb-4">
                                        <Building2 className="h-5 w-5 text-indigo-600" />
                                        <span className="font-medium text-lg">{job.advertiser_name}</span>
                                    </div>
                                </div>
                                {job.company_logo && (
                                    <img
                                        src={job.company_logo}
                                        alt={job.advertiser_name || 'Company Logo'}
                                        className="h-16 w-16 object-contain rounded-lg border border-slate-100"
                                    />
                                )}
                            </div>

                            <div className="flex flex-wrap gap-y-2 gap-x-6 text-sm text-slate-600 mt-2">
                                <div className="flex items-center gap-1.5">
                                    <MapPin className="h-4 w-4 text-slate-400" />
                                    <span>{job.location_label}</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <Clock className="h-4 w-4 text-slate-400" />
                                    <span>{job.work_types_label}</span>
                                </div>
                                {job.salary_label && (
                                    <div className="flex items-center gap-1.5">
                                        <DollarSign className="h-4 w-4 text-slate-400" />
                                        <span>{job.salary_label}</span>
                                    </div>
                                )}
                            </div>

                            <div className="flex flex-wrap gap-2 mt-6">
                                <Badge variant="secondary">{job.classification}</Badge>
                                {job.sub_classification && (
                                    <Badge variant="outline">{job.sub_classification}</Badge>
                                )}
                                <span className="text-xs text-slate-400 flex items-center ml-auto">
                                    Posted {job.listed_at ? formatDistanceToNow(new Date(job.listed_at), { addSuffix: true }) : 'recently'}
                                </span>
                            </div>
                        </div>

                        {/* Job Description */}
                        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
                            <h2 className="text-lg font-semibold text-slate-900 mb-4">Job Description</h2>
                            <div
                                className="prose prose-slate max-w-none prose-headings:text-slate-900 prose-a:text-indigo-600"
                                dangerouslySetInnerHTML={{ __html: job.content || '<p>No description available.</p>' }}
                            />
                        </div>
                    </div>

                    {/* Sidebar */}
                    <div className="space-y-6">
                        {/* Company Info Card (Placeholder) */}
                        <Card>
                            <CardContent className="p-6">
                                <h3 className="font-semibold text-slate-900 mb-4">About the Company</h3>
                                <p className="text-sm text-slate-600 mb-4">
                                    {job.company_name || job.advertiser_name} is a leading company in the {job.classification} sector.
                                </p>
                                <Button variant="outline" className="w-full">
                                    View Company Profile
                                </Button>
                            </CardContent>
                        </Card>

                        {/* Similar Jobs (Placeholder - would use useSimilarJobs hook) */}
                        {/* <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-900 mb-4">Similar Jobs</h3>
              <div className="space-y-4">
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </div>
            </div> */}
                    </div>
                </div>
            </main>
        </div>
    )
}
