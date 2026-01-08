import { useEffect, useState } from 'react'
import { useResumes } from '@/features/resumes/hooks/useResumes'
import { useApplicationMutations } from '@/features/applications/hooks/useApplications'
import { useQuery } from '@tanstack/react-query'
import { jobsApi } from '@/api/jobs'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, AlertCircle } from 'lucide-react'

interface ApplicationDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    jobId: number
    jobTitle: string
}

export function ApplicationDialog({ open, onOpenChange, jobId, jobTitle }: ApplicationDialogProps) {
    const [selectedResumeId, setSelectedResumeId] = useState<string>('')
    const { data: resumesData, isLoading: isLoadingResumes } = useResumes()
    const { createApplication } = useApplicationMutations()
    const { data: matchDetail } = useQuery({
        queryKey: ['job-match-detail', jobId],
        queryFn: () => jobsApi.getJobMatchDetail(jobId),
        enabled: !!jobId,
        retry: false,
    })

    const handleSubmit = () => {
        if (!selectedResumeId) return

        createApplication.mutate(
            {
                job_id: jobId,
                resume_template_id: selectedResumeId,
                tailoring_level: 'light'
            },
            {
                onSuccess: () => {
                    onOpenChange(false)
                    setSelectedResumeId('')
                }
            }
        )
    }

    const resumes = resumesData?.items || []
    const recommendedResumeId = matchDetail?.recommended_resume?.id

    useEffect(() => {
        const recommendedId = matchDetail?.recommended_resume?.id
        if (!recommendedId) return
        if (selectedResumeId) return
        if (!resumes.length) return

        const recommended = resumes.find(r => r.id === recommendedId)
        if (!recommended || recommended.is_draft) return
        setSelectedResumeId(recommendedId)
    }, [matchDetail?.recommended_resume?.id, resumes, selectedResumeId])

    // Check if selected resume is a draft
    const selectedResume = resumes.find(r => r.id === selectedResumeId)
    const isDraftSelected = selectedResume?.is_draft ?? false

    // Check if all resumes are drafts
    const allAreDrafts = resumes.length > 0 && resumes.every(r => r.is_draft)

    // Determine if submit button should be disabled
    const shouldDisableSubmit = !selectedResumeId || isDraftSelected || allAreDrafts || createApplication.isPending

    // Determine warning message
    const showWarning = isDraftSelected || allAreDrafts
    const warningMessage = isDraftSelected
        ? 'This is a draft resume. Please finalize it before applying.'
        : allAreDrafts
        ? 'Only finalized resumes can be used for applications. Please finalize a resume first.'
        : ''

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Apply for {jobTitle}</DialogTitle>
                    <DialogDescription>
                        Select a resume template to tailor for this application. We'll generate a cover letter and a tailored resume for you.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="resume">Resume Template</Label>
                        <Select value={selectedResumeId} onValueChange={setSelectedResumeId}>
                            <SelectTrigger id="resume">
                                <SelectValue placeholder="Select a resume" />
                            </SelectTrigger>
                            <SelectContent>
                                {isLoadingResumes ? (
                                    <div className="flex items-center justify-center p-2">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    </div>
                                ) : resumes.length === 0 ? (
                                    <div className="p-2 text-sm text-slate-500 text-center">
                                        No resumes found. Please create one first.
                                    </div>
                                ) : (
                                    resumes.map((resume) => (
                                        <SelectItem
                                            key={resume.id}
                                            value={resume.id}
                                            className={resume.is_draft ? 'text-slate-400 opacity-60' : ''}
                                        >
                                            <span className="flex items-center gap-2">
                                                {resume.title}
                                                {recommendedResumeId === resume.id && (
                                                    <span className="text-xs px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">
                                                        Recommended
                                                    </span>
                                                )}
                                                {resume.is_draft && (
                                                    <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                                                        Draft
                                                    </span>
                                                )}
                                            </span>
                                        </SelectItem>
                                    ))
                                )}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Warning message for draft resumes */}
                    {showWarning && (
                        <Alert variant="destructive" className="mt-2">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>
                                {warningMessage}
                            </AlertDescription>
                        </Alert>
                    )}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={shouldDisableSubmit}
                    >
                        {createApplication.isPending && (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        Create Application
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
