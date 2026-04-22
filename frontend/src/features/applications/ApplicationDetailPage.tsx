
import { useEffect, useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Building2,
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  MapPin,
} from 'lucide-react'

import {
  useApplication,
  useApplicationCompanyRoles,
  useApplicationMutations,
  useCoverLetterForReview,
  useTailoredResumeForReview,
} from '@/features/applications/hooks/useApplications'
import {
  ApplicationOperationsCard,
  type ApplicationStatusAction,
} from '@/features/applications/components/ApplicationOperationsCard'
import { TimelineCard } from '@/features/applications/components/TimelineCard'
import {
  getApplicationMaterialEmptyMessage,
  getApplicationMaterialState,
} from '@/features/applications/presentation'
import { downloadApplicationPdf } from '@/features/applications/pdf'
import { useJobDetail } from '@/features/jobs/hooks/useJobs'
import { useResumes } from '@/features/resumes/hooks/useResumes'
import { ApplicationResolutionBadge } from '@/features/applications/components/ApplicationResolutionBadge'
import {
  ApplicationStatusBadge,
  getApplicationStatusPresentation,
} from '@/features/applications/components/ApplicationStatusBadge'
import { MarkdownViewer } from '@/components/MarkdownViewer'
import { JobDescriptionHtml } from '@/components/job/JobDescriptionHtml'
import { JobLanguageSelect } from '@/components/job/JobLanguageSelect'
import {
  JobAttributeList,
  JobSourceCompanyLine,
  useSourceDisplay,
} from '@/components/job/jobDisplay'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useToast } from '@/components/ui/use-toast'
import { useAuthStore } from '@/store/authStore'
import type {
  ApplicationCompanyRole,
  ApplicationResolution,
  ApplicationStatus,
  TailoringLevel,
} from '@/types/application'
import type { DocumentEditData } from '@/types/document'
import {
  getListContextKey,
  readSessionRecord,
  type ListOrderState,
  type ListReturnIntent,
  writeSessionRecord,
} from '@/utils/listState'

const STATUS_ACTIONS: Record<ApplicationStatus, ApplicationStatusAction[]> = {
  PENDING: [],
  TAILORING: [],
  READY: [{ label: 'Mark as Applied', nextStatus: 'APPLIED', variant: 'default' }],
  APPLIED: [
    { label: 'Move to Phone Screen', nextStatus: 'PHONE_SCREEN', variant: 'default' },
    { label: 'Mark as Rejected', nextStatus: 'REJECTED', variant: 'outline' },
  ],
  PHONE_SCREEN: [
    { label: 'Move to Interviewing', nextStatus: 'INTERVIEWING', variant: 'default' },
    { label: 'Mark as Rejected', nextStatus: 'REJECTED', variant: 'outline' },
  ],
  INTERVIEWING: [
    { label: 'Mark Offer Received', nextStatus: 'OFFER', variant: 'default' },
    { label: 'Mark as Rejected', nextStatus: 'REJECTED', variant: 'outline' },
  ],
  OFFER: [],
  REJECTED: [],
  FAILED: [],
}

const APPLIED_AND_AFTER_STATUSES: ApplicationStatus[] = [
  'APPLIED',
  'PHONE_SCREEN',
  'INTERVIEWING',
  'OFFER',
  'REJECTED',
]

const APPLICATION_LIST_RETURN_INTENT_KEY = 'applications:list:return-intent'
const APPLICATION_LIST_ORDERS_KEY = 'applications:list:orders'
const APPLICATION_JD_LANGUAGE_STORAGE_KEY = 'application_detail_jd_language'

type DetailNavigationState = {
  previousApplicationId: string | null
  nextApplicationId: string | null
  currentIndex: number | null
  total: number
}

type WorkspaceTab = 'jd' | 'resume' | 'cover-letter'

type ReviewPanelProps = {
  title: string
  document: DocumentEditData | undefined
  isLoading: boolean
  isError: boolean
  isReady: boolean
  editPath?: string
  onDownload?: () => Promise<void>
  isDownloading?: boolean
  onCopy?: () => void
  emptyMessage: string
}

const getContextKey = (params: URLSearchParams): string => getListContextKey('applications:list', params)

function DocumentReviewPanel({
  title,
  document,
  isLoading,
  isError,
  isReady,
  editPath,
  onDownload,
  isDownloading,
  onCopy,
  emptyMessage,
}: ReviewPanelProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!onCopy) return
    onCopy()
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <div>
          <CardTitle>{title}</CardTitle>
          <p className="mt-1 text-sm text-slate-500">
            {isReady ? 'Review the current generated version before applying.' : emptyMessage}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editPath && isReady && (
            <Button asChild variant="outline" size="sm">
              <Link to={editPath}>Edit</Link>
            </Button>
          )}
          {onCopy && isReady && (
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {copied ? (
                <Check className="mr-2 h-4 w-4 text-green-500" />
              ) : (
                <Copy className="mr-2 h-4 w-4" />
              )}
              {copied ? 'Copied!' : 'Copy'}
            </Button>
          )}
          {onDownload && isReady && (
            <Button variant="outline" size="sm" onClick={onDownload} disabled={isDownloading}>
              {isDownloading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              PDF
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-[640px] w-full rounded-xl" />
          </div>
        )}
        {!isLoading && isError && (
          <Alert variant="destructive">
            <AlertTitle>Unable to load {title.toLowerCase()}</AlertTitle>
            <AlertDescription>Please try again later.</AlertDescription>
          </Alert>
        )}
        {!isLoading && !isError && !isReady && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-16 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
              <FileText className="h-6 w-6 text-slate-500" />
            </div>
            <p className="mt-4 text-sm font-medium text-slate-700">{emptyMessage}</p>
          </div>
        )}
        {!isLoading && !isError && isReady && document && (
          <MarkdownViewer content={document.content} />
        )}
      </CardContent>
    </Card>
  )
}

function OtherRolesCard({
  items,
  isLoading,
  searchParams,
}: {
  items: ApplicationCompanyRole[] | undefined
  isLoading: boolean
  searchParams: URLSearchParams
}) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="text-base">Other Roles at This Company</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}
        {!isLoading && (!items || items.length === 0) && (
          <p className="text-sm text-slate-500">No other applications for this company yet.</p>
        )}
        {!isLoading && items && items.length > 0 && (
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                className="rounded-lg border border-slate-200 p-4 transition-colors hover:border-indigo-200"
              >
                <Link
                  to={`/applications/${item.id}${searchParams.toString() ? `?${searchParams.toString()}` : ''}`}
                  className="line-clamp-2 font-semibold text-slate-900 hover:text-indigo-600"
                >
                  {item.job.title}
                </Link>
                <div className="mt-2 space-y-1 text-sm text-slate-600">
                  <div className="flex items-center gap-1.5">
                    <Building2 className="h-3.5 w-3.5 text-slate-400" />
                    <span>{item.job.company_name || item.job.advertiser_name || 'Company'}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-slate-400" />
                    <span>{item.job.location_label || 'Location not specified'}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Clock3 className="h-3.5 w-3.5 text-slate-400" />
                    <span>
                      {item.job.listed_at
                        ? formatDistanceToNow(new Date(item.job.listed_at), { addSuffix: true })
                        : 'recently'}
                    </span>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <ApplicationStatusBadge status={item.status} className="text-[11px]" />
                  {item.resolution !== 'ACTIVE' && (
                    <ApplicationResolutionBadge resolution={item.resolution} className="text-[11px]" />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function ApplicationDetailPage() {
  const { applicationId } = useParams()
  const [searchParams] = useSearchParams()
  const serializedSearchParams = searchParams.toString()
  const { data: application, isLoading, isError } = useApplication(applicationId || '')
  const sourceMeta = useSourceDisplay(application?.job?.source)
  const SourceIcon = sourceMeta.icon
  const { retryCoverLetter, updateStatus, updateResolution } = useApplicationMutations()
  const { data: resumesData, isLoading: isLoadingResumes } = useResumes()
  const { user } = useAuthStore()
  const { toast } = useToast()
  const [isDownloadingResume, setIsDownloadingResume] = useState(false)
  const [isDownloadingCoverLetter, setIsDownloadingCoverLetter] = useState(false)
  const [isRetryDialogOpen, setIsRetryDialogOpen] = useState(false)
  const [retryResumeId, setRetryResumeId] = useState<string>('')
  const [retryTailoringLevel, setRetryTailoringLevel] = useState<TailoringLevel>('light')
  const [jdLanguage, setJdLanguage] = useState<'en' | 'zh'>('en')
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('jd')
  const [forceEditLatest, setForceEditLatest] = useState(false)
  const [detailNavigation, setDetailNavigation] = useState<DetailNavigationState>({
    previousApplicationId: null,
    nextApplicationId: null,
    currentIndex: null,
    total: 0,
  })
  const backUrl = searchParams.toString() ? `/applications?${searchParams.toString()}` : '/applications'
  const { data: jobDetail, isLoading: isJobDetailLoading, isError: isJobDetailError } = useJobDetail(
    activeTab === 'jd' ? application?.job_id ?? null : null,
  )
  const { data: companyRoles, isLoading: isCompanyRolesLoading } = useApplicationCompanyRoles(
    applicationId || '',
    !!applicationId,
  )
  const { data: resumeDocument, isLoading: isResumeLoading, isError: isResumeError } =
    useTailoredResumeForReview(applicationId || '', activeTab === 'resume' && !!application?.resume_document_id)
  const { data: coverLetterDocument, isLoading: isCoverLetterLoading, isError: isCoverLetterError } =
    useCoverLetterForReview(
      applicationId || '',
      activeTab === 'cover-letter' && !!application?.cover_letter_document_id,
    )

  const hasChineseDescription = Boolean(
    jobDetail?.content_cn?.trim() || jobDetail?.analysis?.cn_content?.trim(),
  )

  useEffect(() => {
    const storedLanguage = localStorage.getItem(APPLICATION_JD_LANGUAGE_STORAGE_KEY)
    if (storedLanguage === 'zh' && hasChineseDescription) {
      setJdLanguage('zh')
      return
    }
    setJdLanguage('en')
  }, [application?.job_id, hasChineseDescription])

  useEffect(() => {
    if (!applicationId) return
    const contextKey = getContextKey(searchParams)
    writeSessionRecord<ListReturnIntent<string>>(APPLICATION_LIST_RETURN_INTENT_KEY, {
      current: { contextKey, itemId: applicationId },
    })
  }, [applicationId, searchParams, serializedSearchParams])

  useEffect(() => {
    if (!applicationId) return
    const contextKey = getContextKey(searchParams)
    const orders = readSessionRecord<ListOrderState<string>>(APPLICATION_LIST_ORDERS_KEY)
    const applicationIds = orders[contextKey]?.itemIds || []
    const currentIndex = applicationIds.findIndex((id) => id === applicationId)

    if (currentIndex < 0) {
      setDetailNavigation({
        previousApplicationId: null,
        nextApplicationId: null,
        currentIndex: null,
        total: applicationIds.length,
      })
      return
    }

    setDetailNavigation({
      previousApplicationId: currentIndex > 0 ? applicationIds[currentIndex - 1] : null,
      nextApplicationId: currentIndex < applicationIds.length - 1 ? applicationIds[currentIndex + 1] : null,
      currentIndex,
      total: applicationIds.length,
    })
  }, [applicationId, searchParams, serializedSearchParams])

  const handleDownloadResumePdf = async () => {
    if (!application) return
    setIsDownloadingResume(true)
    try {
      await downloadApplicationPdf({
        applicationId: application.id,
        kind: 'Resume',
        userName: user?.full_name || 'User',
        jobTitle: application.job?.title || 'Job',
      })
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to download PDF',
        variant: 'destructive',
      })
    } finally {
      setIsDownloadingResume(false)
    }
  }

  const handleDownloadCoverLetterPdf = async () => {
    if (!application) return
    setIsDownloadingCoverLetter(true)
    try {
      await downloadApplicationPdf({
        applicationId: application.id,
        kind: 'CoverLetter',
        userName: user?.full_name || 'User',
        jobTitle: application.job?.title || 'Job',
      })
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to download PDF',
        variant: 'destructive',
      })
    } finally {
      setIsDownloadingCoverLetter(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-4">
        <div className="mx-auto max-w-7xl space-y-6">
          <Skeleton className="h-10 w-56" />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Skeleton className="h-[820px] w-full rounded-xl lg:col-span-2" />
            <div className="space-y-4">
              <Skeleton className="h-48 w-full rounded-xl" />
              <Skeleton className="h-52 w-full rounded-xl" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (isError || !application) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <Alert variant="destructive" className="max-w-md">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>Failed to load application details.</AlertDescription>
          <Button asChild variant="outline" className="mt-4 w-full">
            <Link to={backUrl}>Back to Applications</Link>
          </Button>
        </Alert>
      </div>
    )
  }
  const resumes = resumesData?.items || []
  const selectedRetryResume = resumes.find((item) => item.id === retryResumeId)
  const retryDraftSelected = selectedRetryResume?.is_draft ?? false
  const jdHtml =
    jdLanguage === 'zh' && hasChineseDescription
      ? jobDetail?.content_cn || jobDetail?.analysis?.cn_content || jobDetail?.content
      : jobDetail?.content
  const availableStatusActions = STATUS_ACTIONS[application.status] || []
  const isApplicationActive = application.resolution === 'ACTIVE'
  const statusActions = isApplicationActive ? availableStatusActions : []
  const canResolveApplication =
    isApplicationActive &&
    !APPLIED_AND_AFTER_STATUSES.includes(application.status) &&
    !['FAILED'].includes(application.status)
  const statusPresentation = getApplicationStatusPresentation(application.status)
  const primaryAction = statusActions[0] || null
  const secondaryStatusActions = primaryAction
    ? statusActions.filter((action) => action.nextStatus !== primaryAction.nextStatus)
    : statusActions
  const retryVisible = ['READY', 'FAILED'].includes(application.status) && application.resolution === 'ACTIVE'
  const isTailoring = application.status === 'TAILORING'
  const statusDescription = (() => {
    if (application.resolution === 'JOB_CLOSED') {
      return 'This application was stopped because the job was marked closed.'
    }
    if (application.resolution === 'USER_SKIPPED') {
      return 'This application was stopped because you chose to skip it.'
    }
    if (application.resolution === 'STALE_NO_RESPONSE') {
      return 'This application was stopped due to no response.'
    }

    switch (application.status) {
      case 'PENDING':
        return 'Application created. Materials have not started generating yet.'
      case 'READY':
        return 'Materials are ready. Review them, apply externally, then mark as applied.'
      case 'TAILORING':
        return 'Resume and cover letter are being generated.'
      case 'PHONE_SCREEN':
        return 'Phone screen in progress. Move forward when the next stage is confirmed.'
      case 'INTERVIEWING':
        return 'Interview process in progress. Update the status after each outcome.'
      case 'OFFER':
        return 'Offer received. Keep this application updated with your final decision.'
      case 'REJECTED':
        return 'Application closed as rejected.'
      case 'FAILED':
        return 'Generation failed. Retry to regenerate the materials.'
      case 'APPLIED':
        return 'Application submitted. Update the pipeline as responses come in.'
      default:
        return 'Review materials and continue here.'
    }
  })()
  const resumeMaterialState = getApplicationMaterialState(application, 'resume')
  const coverLetterMaterialState = getApplicationMaterialState(application, 'coverLetter')
  const resumeEmptyMessage = getApplicationMaterialEmptyMessage(application.status, 'resume')
  const coverLetterEmptyMessage = getApplicationMaterialEmptyMessage(application.status, 'coverLetter')
  const isInactiveResolution =
    application.resolution === 'JOB_CLOSED' || application.resolution === 'USER_SKIPPED'

  const openRetryDialog = () => {
    setRetryResumeId(application.source_resume_id)
    setRetryTailoringLevel(application.tailoring_level)
    setIsRetryDialogOpen(true)
  }

  const submitRetry = () => {
    if (!retryResumeId || retryDraftSelected) return
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
          setIsRetryDialogOpen(false)
        },
      },
    )
  }

  const handleStatusUpdate = (status: ApplicationStatus) => {
    updateStatus.mutate({ id: application.id, status }, { onSuccess: () => setForceEditLatest(true) })
  }

  const handleResolutionUpdate = (resolution: ApplicationResolution) => {
    updateResolution.mutate({ id: application.id, resolution })
  }

  const handleJdLanguageChange = (value: string) => {
    if (value === 'zh' && !hasChineseDescription) return
    const nextLanguage = value === 'zh' ? 'zh' : 'en'
    setJdLanguage(nextLanguage)
    localStorage.setItem(APPLICATION_JD_LANGUAGE_STORAGE_KEY, nextLanguage)
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      <div className="sticky top-0 z-20 border-b border-slate-200 bg-slate-50/95 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" asChild className="text-slate-600">
                <Link to={backUrl}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Applications
                </Link>
              </Button>
              {detailNavigation.total > 0 && detailNavigation.currentIndex !== null && (
                <span className="text-sm text-slate-500">
                  {detailNavigation.currentIndex + 1} / {detailNavigation.total}
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {detailNavigation.previousApplicationId ? (
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/applications/${detailNavigation.previousApplicationId}?${searchParams.toString()}`}>
                    <ChevronLeft className="mr-1 h-4 w-4" />
                    Previous
                  </Link>
                </Button>
              ) : (
                <Button variant="outline" size="sm" disabled>
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  Previous
                </Button>
              )}
              {detailNavigation.nextApplicationId ? (
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/applications/${detailNavigation.nextApplicationId}?${searchParams.toString()}`}>
                    Next
                    <ChevronRight className="ml-1 h-4 w-4" />
                  </Link>
                </Button>
              ) : (
                <Button variant="outline" size="sm" disabled>
                  Next
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                asChild={Boolean(application.job?.share_link)}
                disabled={!application.job?.share_link}
              >
                {application.job?.share_link ? (
                  <a
                    href={application.job.share_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Apply on ${sourceMeta.label}`}
                    className="inline-flex items-center gap-2"
                  >
                    <span>Apply on</span>
                    {sourceMeta.iconSrc ? (
                      <img
                        src={sourceMeta.iconSrc}
                        alt={`${sourceMeta.label} icon`}
                        className="h-4 w-4 rounded-sm object-contain"
                      />
                    ) : SourceIcon ? (
                      <SourceIcon className="h-4 w-4" />
                    ) : null}
                  </a>
                ) : (
                  <span>Apply on Source Site</span>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card className="border-slate-200 shadow-sm">
              <CardContent className="space-y-5 p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h1 className="text-2xl font-bold text-slate-900">{application.job?.title || 'Unknown Job'}</h1>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button variant="ghost" size="icon" asChild className="h-8 w-8 text-slate-500 hover:text-slate-700">
                              <Link to={`/jobs/${application.job_id}`} aria-label="View job details">
                                <ExternalLink className="h-4 w-4" />
                              </Link>
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>View job details</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <JobSourceCompanyLine
                      source={application.job?.source}
                      companyName={application.job?.company_name}
                      advertiserName={application.job?.advertiser_name}
                      className="mt-2 text-lg"
                    />
                  </div>
                  {application.job?.company_logo && (
                    <img
                      src={application.job.company_logo}
                      alt={application.job?.title || 'Company logo'}
                      className="h-16 w-16 rounded-lg object-contain"
                    />
                  )}
                </div>

                <JobAttributeList job={application.job ?? {}} className="text-sm text-slate-600" showCategory={false} showSalary={true} />

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-1.5 text-sm text-slate-500">
                    <Calendar className="h-4 w-4" />
                    <span>
                      Added {formatDistanceToNow(new Date(application.created_at), { addSuffix: true })}
                    </span>
                  </div>
                  {application.last_error && (
                    <Badge className="bg-red-500 text-white hover:bg-red-600">{statusPresentation.label}: issue detected</Badge>
                  )}
                </div>
              </CardContent>
            </Card>

            {application.last_error && (
              <Alert variant="destructive">
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{application.last_error}</AlertDescription>
              </Alert>
            )}

            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as WorkspaceTab)} className="space-y-4">
              <TabsList className="grid h-auto w-full grid-cols-3 rounded-xl bg-slate-200/70 p-1">
                <TabsTrigger value="jd" className="rounded-lg py-2.5">
                  JD
                </TabsTrigger>
                <TabsTrigger value="resume" className="rounded-lg py-2.5">
                  Resume
                </TabsTrigger>
                <TabsTrigger value="cover-letter" className="rounded-lg py-2.5">
                  Cover Letter
                </TabsTrigger>
              </TabsList>

              <TabsContent value="jd" className="mt-0">
                <Card className="border-slate-200 shadow-sm">
                  <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
                    <div>
                      <CardTitle>Job Description</CardTitle>
                      <p className="mt-1 text-sm text-slate-500">
                        Compare the posting against your tailored materials before applying.
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <JobLanguageSelect
                        value={jdLanguage}
                        onValueChange={handleJdLanguageChange}
                        hasChinese={hasChineseDescription}
                      />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {isJobDetailLoading && (
                      <div className="space-y-3">
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-2/3" />
                        <Skeleton className="h-64 w-full" />
                      </div>
                    )}
                    {!isJobDetailLoading && isJobDetailError && (
                      <Alert variant="destructive">
                        <AlertTitle>Error</AlertTitle>
                        <AlertDescription>Failed to load JD details.</AlertDescription>
                      </Alert>
                    )}
                    {!isJobDetailLoading && !isJobDetailError && <JobDescriptionHtml html={jdHtml} />}
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="resume" className="mt-0">
                <DocumentReviewPanel
                  title="Resume"
                  document={resumeDocument}
                  isLoading={isResumeLoading}
                  isError={isResumeError}
                  isReady={Boolean(application.resume_document_id)}
                  editPath={`/applications/${application.id}/resume`}
                  onDownload={handleDownloadResumePdf}
                  isDownloading={isDownloadingResume}
                  emptyMessage={resumeEmptyMessage}
                />
              </TabsContent>

              <TabsContent value="cover-letter" className="mt-0">
                <DocumentReviewPanel
                  title="Cover Letter"
                  document={coverLetterDocument}
                  isLoading={isCoverLetterLoading}
                  isError={isCoverLetterError}
                  isReady={Boolean(application.cover_letter_document_id)}
                  editPath={`/applications/${application.id}/cover-letter`}
                  onDownload={handleDownloadCoverLetterPdf}
                  isDownloading={isDownloadingCoverLetter}
                  onCopy={
                    coverLetterDocument?.content
                      ? () => navigator.clipboard.writeText(coverLetterDocument.content)
                      : undefined
                  }
                  emptyMessage={coverLetterEmptyMessage}
                />
              </TabsContent>
            </Tabs>

          </div>

          <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            <ApplicationOperationsCard
              application={application}
              statusDescription={statusDescription}
              isInactiveResolution={isInactiveResolution}
              isTailoring={isTailoring}
              primaryAction={primaryAction}
              secondaryStatusActions={secondaryStatusActions}
              canResolveApplication={canResolveApplication}
              resumeMaterialState={resumeMaterialState}
              coverLetterMaterialState={coverLetterMaterialState}
              isDownloadingResume={isDownloadingResume}
              isDownloadingCoverLetter={isDownloadingCoverLetter}
              retryVisible={retryVisible}
              isUpdateStatusPending={updateStatus.isPending}
              isUpdateResolutionPending={updateResolution.isPending}
              isRetryPending={retryCoverLetter.isPending}
              onStatusUpdate={handleStatusUpdate}
              onResolutionUpdate={handleResolutionUpdate}
              onDownloadResumePdf={handleDownloadResumePdf}
              onDownloadCoverLetterPdf={handleDownloadCoverLetterPdf}
              onOpenRetryDialog={openRetryDialog}
            />
            <TimelineCard
              applicationId={application.id}
              forceEditLatest={forceEditLatest}
              onForceEditLatestConsumed={() => setForceEditLatest(false)}
            />
            <OtherRolesCard items={companyRoles} isLoading={isCompanyRolesLoading} searchParams={searchParams} />
          </aside>
        </div>
      </main>

      <Dialog open={isRetryDialogOpen} onOpenChange={setIsRetryDialogOpen}>
        <DialogContent className="sm:max-w-[460px]">
          <DialogHeader>
            <DialogTitle>Retry Generation</DialogTitle>
            <DialogDescription>
              Select a resume template and tailoring level, then rerun resume tailoring and cover letter generation.
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
                    <div className="px-3 py-2 text-sm text-slate-500">Loading resumes...</div>
                  ) : resumes.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-slate-500">No resumes found</div>
                  ) : (
                    resumes.map((resume) => (
                      <SelectItem key={resume.id} value={resume.id}>
                        <span className="flex items-center gap-2">
                          {resume.title}
                          {resume.is_draft && (
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">Draft</span>
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
                onValueChange={(value) => setRetryTailoringLevel(value as TailoringLevel)}
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
                  Draft resume cannot be used for retry. Please choose a finalized resume.
                </AlertDescription>
              </Alert>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRetryDialogOpen(false)} disabled={retryCoverLetter.isPending}>
              Cancel
            </Button>
            <Button
              onClick={submitRetry}
              disabled={!retryResumeId || retryDraftSelected || retryCoverLetter.isPending}
            >
              {retryCoverLetter.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Retry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
