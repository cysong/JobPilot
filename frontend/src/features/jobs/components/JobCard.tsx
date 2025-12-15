import { MapPin, Building2, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Link, useSearchParams } from 'react-router-dom'

import type { Job } from '@/types/job'
import { Badge } from '@/components/ui/badge'
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
} from '@/components/ui/card'

interface JobCardProps {
    job: Job
}

export function JobCard({ job }: JobCardProps) {
    const [searchParams] = useSearchParams()

    // Preserve current search params when navigating to detail page
    const detailUrl = `/jobs/${job.id}?${searchParams.toString()}`
    return (
        <Card className="hover:shadow-md transition-shadow border-slate-200">
            <CardHeader className="p-4 pb-2">
                <div className="flex justify-between items-start gap-4">
                    <div className="space-y-1">
                        <Link
                            to={detailUrl}
                            className="font-semibold text-lg text-slate-900 hover:text-indigo-600 line-clamp-2"
                        >
                            {job.title}
                        </Link>
                        <div className="flex items-center gap-2 text-sm text-slate-600">
                            <Building2 className="h-4 w-4" />
                            <span className="font-medium">{job.advertiser_name}</span>
                        </div>
                    </div>
                    {job.company_logo && (
                        <img
                            src={job.company_logo}
                            alt={`${job.advertiser_name} logo`}
                            className="h-12 w-12 object-contain rounded-md"
                        />
                    )}
                </div>
            </CardHeader>
            <CardContent className="p-4 pt-2 space-y-3">
                <div className="flex flex-wrap gap-y-2 gap-x-4 text-sm text-slate-500">
                    <div className="flex items-center gap-1">
                        <MapPin className="h-3.5 w-3.5" />
                        <span>{job.location_label}</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        <span>{job.work_types_label}</span>
                    </div>
                    {job.salary_label && (
                    <div className="flex items-center gap-1">
                        <span>{job.salary_label}</span>
                    </div>
                    )}
                </div>

                {job.abstract && (
                    <p className="text-sm text-slate-600 line-clamp-2">
                        {job.abstract}
                    </p>
                )}

                <div className="flex flex-wrap gap-2 pt-1">
                    <Badge variant="secondary" className="font-normal text-xs">
                        {job.classification}
                    </Badge>
                    {job.sub_classification && (
                        <Badge variant="outline" className="font-normal text-xs text-slate-500">
                            {job.sub_classification}
                        </Badge>
                    )}
                </div>
            </CardContent>
            <CardFooter className="p-4 pt-0 text-xs text-slate-400">
                <span>
                    Listed {job.listed_at ? formatDistanceToNow(new Date(job.listed_at), { addSuffix: true }) : 'recently'}
                </span>
            </CardFooter>
        </Card>
    )
}
