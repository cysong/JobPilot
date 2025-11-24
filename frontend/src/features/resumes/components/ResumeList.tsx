import type { ResumeListItem } from '@/types/resume'
import { ResumeCard } from './ResumeCard'
import { Skeleton } from '@/components/ui/skeleton'

interface ResumeListProps {
    resumes: ResumeListItem[]
    isLoading: boolean
    onDelete: (id: string) => void
}

export function ResumeList({ resumes, isLoading, onDelete }: ResumeListProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="bg-white p-6 rounded-xl border border-slate-200 space-y-4">
                        <Skeleton className="h-12 w-12 rounded-lg" />
                        <div className="space-y-2">
                            <Skeleton className="h-5 w-3/4" />
                            <Skeleton className="h-4 w-1/2" />
                        </div>
                        <div className="flex gap-2 pt-2">
                            <Skeleton className="h-5 w-12" />
                            <Skeleton className="h-5 w-12" />
                        </div>
                    </div>
                ))}
            </div>
        )
    }

    if (resumes.length === 0) {
        return (
            <div className="text-center py-12 bg-white rounded-xl border border-slate-200">
                <div className="mx-auto w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mb-4">
                    <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                </div>
                <h3 className="text-lg font-medium text-slate-900">No resumes yet</h3>
                <p className="text-slate-500 mt-1">Create your first resume to get started.</p>
            </div>
        )
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {resumes.map((resume) => (
                <ResumeCard key={resume.id} resume={resume} onDelete={onDelete} />
            ))}
        </div>
    )
}
