import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { format } from 'date-fns';
import {
    ArrowLeft,
    Building2,
    Calendar,
    FileText,
    Download,
    ExternalLink,
    RefreshCw,
    Loader2,
} from 'lucide-react';

import { useApplication, useApplicationMutations } from '@/features/applications/hooks/useApplications';
import { useResumes } from '@/features/resumes/hooks/useResumes';
import { applicationApi } from '@/api/applications';
import { ApplicationStatusBadge } from '@/features/applications/components/ApplicationStatusBadge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { Label } from '@/components/ui/label';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/components/ui/use-toast';
import { useAuthStore } from '@/store/authStore';
import type { TailoringLevel } from '@/types/application';

const toSafeFilename = (value: string) => {
    const cleaned = value.replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '')
    return cleaned || 'document'
}

export default function ApplicationDetailPage() {
    const { applicationId } = useParams();
    const { data: application, isLoading, isError } = useApplication(applicationId || '');
    const { retryCoverLetter } = useApplicationMutations();
    const { data: resumesData, isLoading: isLoadingResumes } = useResumes();
    const { user } = useAuthStore();
    const { toast } = useToast();
    const [isDownloadingResume, setIsDownloadingResume] = useState(false);
    const [isDownloadingCoverLetter, setIsDownloadingCoverLetter] = useState(false);
    const [isRetryDialogOpen, setIsRetryDialogOpen] = useState(false);
    const [retryResumeId, setRetryResumeId] = useState<string>('');
    const [retryTailoringLevel, setRetryTailoringLevel] = useState<TailoringLevel>('light');

    const buildFilename = (label: string) => {
        const jobTitle = application?.job?.title || 'Job';
        const userName = user?.full_name || 'User';
        return `${toSafeFilename(`${userName}_${label}_${jobTitle}`)}.pdf`;

    };

    const handleDownloadResumePdf = async () => {
        if (!application) return;
        setIsDownloadingResume(true);
        try {
            const blob = await applicationApi.exportTailoredResumePdf(application.id);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = buildFilename('Resume');
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            toast({
                title: 'Error',
                description: 'Failed to download PDF',
                variant: 'destructive',
            });
        } finally {
            setIsDownloadingResume(false);
        }
    };

    const handleDownloadCoverLetterPdf = async () => {
        if (!application) return;
        setIsDownloadingCoverLetter(true);
        try {
            const blob = await applicationApi.exportCoverLetterPdf(application.id);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = buildFilename('CoverLetter');
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            toast({
                title: 'Error',
                description: 'Failed to download PDF',
                variant: 'destructive',
            });
        } finally {
            setIsDownloadingCoverLetter(false);
        }
    };

    if (isLoading) {
        return (
            <div className="min-h-screen bg-slate-50 p-4">
                <div className="max-w-4xl mx-auto space-y-6">
                    <Skeleton className="h-8 w-32" />
                    <div className="bg-white p-8 rounded-xl border border-slate-200 space-y-6">
                        <Skeleton className="h-10 w-3/4" />
                        <Skeleton className="h-6 w-1/2" />
                        <Separator />
                        <Skeleton className="h-32 w-full" />
                    </div>
                </div>
            </div>
        );
    }

    if (isError || !application) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
                <Alert variant="destructive" className="max-w-md">
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>
                        Failed to load application details.
                    </AlertDescription>
                    <Button asChild variant="outline" className="mt-4 w-full">
                        <Link to="/applications">Back to Applications</Link>
                    </Button>
                </Alert>
            </div>
        );
    }

    const company = application.job?.company_name || application.job?.advertiser_name || 'Unknown Company';
    const resumes = resumesData?.items || [];
    const selectedRetryResume = resumes.find((item) => item.id === retryResumeId);
    const retryDraftSelected = selectedRetryResume?.is_draft ?? false;

    const openRetryDialog = () => {
        setRetryResumeId(application.source_resume_id);
        setRetryTailoringLevel(application.tailoring_level);
        setIsRetryDialogOpen(true);
    };

    const submitRetry = () => {
        if (!retryResumeId || retryDraftSelected) return;
        retryCoverLetter.mutate(
            {
                id: application.id,
                payload: {
                    resume_template_id: retryResumeId,
                    tailoring_level: retryTailoringLevel,
                },
            },
            {
                onSuccess: () => {
                    setIsRetryDialogOpen(false);
                },
            }
        );
    };

    return (
      <div className="min-h-screen bg-slate-50 pb-12">
        {/* Header */}
        <div className="bg-white border-b border-slate-200 sticky top-0 z-20">
          <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              asChild
              className="-ml-2 text-slate-600"
            >
              <Link to="/applications">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Applications
              </Link>
            </Button>
            <ApplicationStatusBadge status={application.status} />
          </div>
        </div>

        <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
          {/* Job Info Card */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-2xl font-bold text-slate-900">
                    {application.job?.title || "Unknown Job"}
                  </CardTitle>
                  <div className="flex items-center gap-2 text-slate-600 mt-2">
                    <Building2 className="h-5 w-5 text-indigo-600" />
                    <span className="font-medium">{company}</span>
                  </div>
                </div>
                {application.job?.company_logo && (
                  <img
                    src={application.job.company_logo}
                    alt={company}
                    className="h-16 w-16 object-contain rounded-lg"
                  />
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4 text-sm text-slate-600">
                <div className="flex items-center gap-1.5">
                  <Calendar className="h-4 w-4" />
                  <span>
                    Applied{" "}
                    {format(new Date(application.created_at), "MMM d, yyyy")}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Error Message */}
          {application.last_error && (
            <Alert variant="destructive">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{application.last_error}</AlertDescription>
            </Alert>
          )}

          {/* Documents Card */}
          <Card>
            <CardHeader>
              <CardTitle>Application Materials</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Resume */}
              <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                {application.resume_document_id ? (
                  <Link
                    to={`/applications/${application.id}/resume`}
                    className="flex items-center gap-3 group"
                  >
                    <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <FileText className="h-5 w-5 text-indigo-600" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-900 group-hover:text-indigo-700">
                        Resume
                      </div>
                      <div className="text-sm text-slate-500">Ready</div>
                    </div>
                  </Link>
                ) : (
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <FileText className="h-5 w-5 text-indigo-600" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">Resume</div>
                      <div className="text-sm text-slate-500">
                        Processing...
                      </div>
                    </div>
                  </div>
                )}
                {application.resume_document_id && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadResumePdf}
                    disabled={isDownloadingResume}
                  >
                    {isDownloadingResume ? (
                      <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                    ) : (
                      <Download className="h-3.5 w-3.5 mr-2" />
                    )}
                    PDF
                  </Button>
                )}
              </div>

              {/* Cover Letter */}
              <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                {application.cover_letter_document_id ? (
                  <Link
                    to={`/applications/${application.id}/cover-letter`}
                    className="flex items-center gap-3 group"
                  >
                    <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <FileText className="h-5 w-5 text-indigo-600" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-900 group-hover:text-indigo-700">
                        Cover Letter
                      </div>
                      <div className="text-sm text-slate-500">Ready</div>
                    </div>
                  </Link>
                ) : (
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <FileText className="h-5 w-5 text-indigo-600" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">
                        Cover Letter
                      </div>
                      <div className="text-sm text-slate-500">
                        Processing...
                      </div>
                    </div>
                  </div>
                )}
                {application.cover_letter_document_id && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadCoverLetterPdf}
                    disabled={isDownloadingCoverLetter}
                  >
                    {isDownloadingCoverLetter ? (
                      <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                    ) : (
                      <Download className="h-3.5 w-3.5 mr-2" />
                    )}
                    PDF
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex gap-2 justify-end">
            <Button variant="outline" asChild>
              <Link to={`/jobs/${application.job_id}`}>
                <ExternalLink className="h-4 w-4 mr-2" />
                View Job
              </Link>
            </Button>
            <Button
              variant="default"
              onClick={openRetryDialog}
              disabled={retryCoverLetter.isPending}
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${
                  retryCoverLetter.isPending ? "animate-spin" : ""
                }`}
              />
              Retry Generation
            </Button>
          </div>
        </main>

        <Dialog open={isRetryDialogOpen} onOpenChange={setIsRetryDialogOpen}>
          <DialogContent className="sm:max-w-[460px]">
            <DialogHeader>
              <DialogTitle>Retry Generation</DialogTitle>
              <DialogDescription>
                Select a resume template and tailoring level, then rerun resume
                tailoring and cover letter generation.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="grid gap-2">
                <Label htmlFor="retry-resume">Resume Template</Label>
                <Select value={retryResumeId} onValueChange={setRetryResumeId}>
                  <SelectTrigger id="retry-resume">
                    <SelectValue placeholder="Select a resume" />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoadingResumes ? (
                      <div className="px-3 py-2 text-sm text-slate-500">
                        Loading resumes...
                      </div>
                    ) : resumes.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-slate-500">
                        No resumes found
                      </div>
                    ) : (
                      resumes.map((resume) => (
                        <SelectItem key={resume.id} value={resume.id}>
                          <span className="flex items-center gap-2">
                            {resume.title}
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

              <div className="grid gap-2">
                <Label htmlFor="retry-tailoring-level">Tailoring Level</Label>
                <Select
                  value={retryTailoringLevel}
                  onValueChange={(value) =>
                    setRetryTailoringLevel(value as TailoringLevel)
                  }
                >
                  <SelectTrigger id="retry-tailoring-level">
                    <SelectValue placeholder="Select tailoring level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">Light</SelectItem>
                    <SelectItem value="moderate">Moderate</SelectItem>
                    <SelectItem value="deep">Deep</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {retryDraftSelected && (
                <Alert variant="destructive">
                  <AlertDescription>
                    Draft resume cannot be used for retry. Please choose a
                    finalized resume.
                  </AlertDescription>
                </Alert>
              )}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsRetryDialogOpen(false)}
                disabled={retryCoverLetter.isPending}
              >
                Cancel
              </Button>
              <Button
                onClick={submitRetry}
                disabled={
                  !retryResumeId ||
                  retryDraftSelected ||
                  retryCoverLetter.isPending
                }
              >
                {retryCoverLetter.isPending && (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                )}
                Retry
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
}
