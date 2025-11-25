import { useState } from 'react'
import { useResumes } from '@/features/resumes/hooks/useResumes'
import { useApplicationMutations } from '@/features/applications/hooks/useApplications'
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
import { Loader2 } from 'lucide-react'

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
                                        <SelectItem key={resume.id} value={resume.id}>
                                            {resume.title}
                                        </SelectItem>
                                    ))
                                )}
                            </SelectContent>
                        </Select>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!selectedResumeId || createApplication.isPending}
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
