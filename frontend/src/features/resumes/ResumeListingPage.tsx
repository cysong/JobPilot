import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useFormalResumeLimit, useResumes, useResumeMutations } from '@/features/resumes/hooks/useResumes'
import { ResumeList } from '@/features/resumes/components/ResumeList'
import { Button } from '@/components/ui/button'

export default function ResumeListingPage() {
    const { data, isLoading } = useResumes()
    const { data: formalLimit } = useFormalResumeLimit()
    const { deleteResume } = useResumeMutations()
    const subtitle = formalLimit?.limit == null
        ? 'Finalize resumes to join matching.'
        : `Finalize resumes to join matching. Max ${formalLimit.limit}.`

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">My Resumes</h1>
                    <p className="text-slate-500 mt-1">{subtitle}</p>
                </div>
                <Link to="/resumes/new">
                    <Button className="bg-indigo-600 hover:bg-indigo-700">
                        <Plus className="w-4 h-4 mr-2" />
                        Create New
                    </Button>
                </Link>
            </div>

            <ResumeList
                resumes={data?.items || []}
                isLoading={isLoading}
                onDelete={(id) => deleteResume.mutate(id)}
            />
        </div>
    )
}
