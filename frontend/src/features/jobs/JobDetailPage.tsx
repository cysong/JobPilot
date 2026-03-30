import { useEffect, useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import {
  Building2,
  MapPin,
  Clock,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Share2,
  Plus,
  Eye,
  Star,
  Users,
  Code2,
  Zap,
} from "lucide-react";

import {
  useJobDetail,
  useJobExpirationMutations,
  useJobSavedMutations,
  useJobSavedStatus,
  useSimilarJobs,
  useJobViewedMutations,
} from "@/features/jobs/hooks/useJobs";
import { useApplicationByJob } from "@/features/applications/hooks/useApplicationByJob";
import { ApplicationDialog } from "@/features/applications/components/ApplicationDialog";
import { getApplicationStatusPresentation } from "@/features/applications/components/ApplicationStatusBadge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { JobDescriptionHtml } from "@/components/job/JobDescriptionHtml";
import { JobLanguageSelect } from "@/components/job/JobLanguageSelect";
import {
  JobAttributeList,
  formatJobCategory,
  getCompanyDisplayName,
  getSourceMeta,
  JobSourceCompanyLine,
} from "@/components/job/jobDisplay";
import { cn } from "@/utils/cn";
import {
  getListContextKey,
  readSessionRecord,
  type ListOrderState,
  type ListReturnIntent,
  writeSessionRecord,
} from "@/utils/listState";

const LANGUAGE_STORAGE_KEY = "job_detail_language";
const JOB_LIST_RETURN_INTENT_KEY = "jobs:list:return-intent";
const JOB_LIST_ORDERS_KEY = "jobs:list:orders";
const VIEWED_DEDUP_WINDOW_MS = 60 * 1000;
type DetailNavigationState = {
  previousJobId: number | null;
  nextJobId: number | null;
  currentIndex: number | null;
  total: number;
};

const getContextKey = (params: URLSearchParams): string => getListContextKey("jobs:list", params);

export default function JobDetailPage() {
  const { jobId } = useParams();
  const [searchParams] = useSearchParams();
  const serializedSearchParams = searchParams.toString();
  const [isApplicationDialogOpen, setIsApplicationDialogOpen] = useState(false);
  const [language, setLanguage] = useState<"en" | "zh">("en");
  const [detailNavigation, setDetailNavigation] = useState<DetailNavigationState>({
    previousJobId: null,
    nextJobId: null,
    currentIndex: null,
    total: 0,
  });
  const jobIdNum = parseInt(jobId || "0");
  const {
    data: job,
    isLoading,
    isError,
  } = useJobDetail(jobIdNum);
  const {
    data: similarJobs,
    isLoading: isSimilarJobsLoading,
  } = useSimilarJobs(jobIdNum, 5);
  const { data: savedStatus } = useJobSavedStatus(jobIdNum);
  const { saveJob, unsaveJob } = useJobSavedMutations();
  const { setJobExpiration } = useJobExpirationMutations();
  const { markViewed } = useJobViewedMutations();

  const hasCn = Boolean(job?.content_cn?.trim() || job?.analysis?.cn_content?.trim());

  useEffect(() => {
    const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (storedLanguage === "zh" && hasCn) {
      setLanguage("zh");
      return;
    }
    setLanguage("en");
  }, [jobIdNum, hasCn]);

  useEffect(() => {
    if (!jobIdNum) return;
    const contextKey = getContextKey(searchParams);
    writeSessionRecord<ListReturnIntent<number>>(JOB_LIST_RETURN_INTENT_KEY, {
      current: { contextKey, itemId: jobIdNum },
    });
  }, [jobIdNum, serializedSearchParams, searchParams]);

  useEffect(() => {
    if (!jobIdNum) return;

    const dedupeKey = `jobs:viewed:last:${jobIdNum}`;
    const lastMarkedAt = Number(sessionStorage.getItem(dedupeKey) || "0");
    const now = Date.now();
    if (now - lastMarkedAt < VIEWED_DEDUP_WINDOW_MS) return;

    sessionStorage.setItem(dedupeKey, String(now));
    markViewed.mutate({ jobId: jobIdNum });
  }, [jobIdNum, markViewed]);

  useEffect(() => {
    if (!jobIdNum) return;
    const contextKey = getContextKey(searchParams);

    const orders = readSessionRecord<ListOrderState<number>>(JOB_LIST_ORDERS_KEY);
    const jobIds = orders[contextKey]?.itemIds || [];
    const currentIndex = jobIds.findIndex((id) => id === jobIdNum);

    if (currentIndex < 0) {
      setDetailNavigation({
        previousJobId: null,
        nextJobId: null,
        currentIndex: null,
        total: jobIds.length,
      });
      return;
    }

    setDetailNavigation({
      previousJobId: currentIndex > 0 ? jobIds[currentIndex - 1] : null,
      nextJobId: currentIndex < jobIds.length - 1 ? jobIds[currentIndex + 1] : null,
      currentIndex,
      total: jobIds.length,
    });
  }, [jobIdNum, searchParams, serializedSearchParams]);

  const handleLanguageChange = (value: string) => {
    if (value === "zh" && !hasCn) return;
    const nextLanguage = value === "zh" ? "zh" : "en";
    setLanguage(nextLanguage);
    localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
  };

  // Query for existing application
  const {
    data: application,
    isLoading: isApplicationLoading,
  } = useApplicationByJob(jobIdNum);
  const applicationStatusPresentation = application
    ? getApplicationStatusPresentation(application.status)
    : null;

  // Restore search params when going back to listing page
  const backUrl = `/jobs?${searchParams.toString()}`;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-4">
        <div className="px-4">
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
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <Alert variant="destructive" className="max-w-md">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            Failed to load job details. The job may have expired or been
            removed.
          </AlertDescription>
          <Button asChild variant="outline" className="mt-4 w-full">
            <Link to={backUrl}>Back to Jobs</Link>
          </Button>
        </Alert>
      </div>
    );
  }

  const descriptionHtml =
    language === "zh" && hasCn
      ? job.content_cn || job.analysis?.cn_content || job.content
      : job.content;
  const isSaved = Boolean(savedStatus?.is_saved);
  const categoryText = formatJobCategory(job);
  const sourceMeta = getSourceMeta(job.source);
  const SourceIcon = sourceMeta.icon;

  const handleToggleSaved = () => {
    if (isSaved) {
      unsaveJob.mutate({ jobId: job.id });
      return;
    }
    saveJob.mutate({ jobId: job.id, job });
  };

  const handleToggleExpiration = () => {
    setJobExpiration.mutate({
      jobId: job.id,
      manualExpired: !job.manual_expired,
    });
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      {/* Header Navigation */}
      <div className="px-4">
        <div className="bg-white border-b border-slate-200 sticky top-0 z-20">
          <div className="px-4 h-16 flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              asChild
              className="-ml-2 text-slate-600"
            >
              <Link to={backUrl}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Search
              </Link>
            </Button>
	            <div className="flex gap-2 items-center">
	              {detailNavigation.previousJobId ? (
	                <Button variant="outline" size="sm" asChild>
                  <Link
                    to={`/jobs/${detailNavigation.previousJobId}?${searchParams.toString()}`}
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" />
                    Previous
                  </Link>
                </Button>
              ) : (
                <Button variant="outline" size="sm" disabled>
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
              )}
              {detailNavigation.nextJobId ? (
                <Button variant="outline" size="sm" asChild>
                  <Link
                    to={`/jobs/${detailNavigation.nextJobId}?${searchParams.toString()}`}
                  >
                    Next
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Link>
                </Button>
	              ) : (
	                <Button variant="outline" size="sm" disabled>
	                  Next
	                  <ChevronRight className="h-4 w-4 ml-1" />
	                </Button>
	              )}
	              {job.share_link && (
	                <Button variant="outline" size="sm" asChild>
	                  <a
	                    href={job.share_link}
	                    target="_blank"
	                    rel="noopener noreferrer"
	                    aria-label="Open Original Posting"
	                    className="inline-flex items-center gap-2"
	                  >
	                    <span>Open on</span>
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
	                </Button>
	              )}
	              <Button variant="outline" size="sm">
	                <Share2 className="h-4 w-4 mr-2" />
	                Share
	              </Button>
            </div>

            <ApplicationDialog
              open={isApplicationDialogOpen}
              onOpenChange={setIsApplicationDialogOpen}
              jobId={job.id}
              jobTitle={job.title}
            />
          </div>
        </div>
      </div>

      <main className="px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Job Header Card */}
            <div className="relative bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              {/* Company logo - absolute positioned at Card level, independent of all content */}
              {job.company_logo && (
                <img
                  src={job.company_logo}
                  alt={job.advertiser_name || "Company Logo"}
                  className="absolute top-6 right-6 h-20 w-auto max-w-[100px] object-contain rounded-lg z-10"
                />
              )}

	              <div className="pr-28">
	                <div className="mb-2">
	                  <h1 className="text-2xl font-bold leading-tight text-slate-900">
	                    <span>{job.title}</span>
	                    <span className="ml-2 inline-flex items-center gap-2 align-middle">
	                      <TooltipProvider>
	                        <Tooltip>
	                          <TooltipTrigger asChild>
	                            <Button
	                              variant="ghost"
	                              size="icon"
	                              onClick={handleToggleSaved}
	                              disabled={saveJob.isPending || unsaveJob.isPending}
	                              aria-label={isSaved ? "Unsave job" : "Save job"}
	                              className={cn(
	                                "inline-flex h-8 w-8 align-middle text-slate-500 hover:text-amber-600",
	                                isSaved && "text-amber-500 hover:text-amber-600",
	                              )}
	                            >
	                              <Star
	                                className={cn(
	                                  "h-4 w-4",
	                                  isSaved && "fill-amber-500 text-amber-500",
	                                )}
	                              />
	                            </Button>
	                          </TooltipTrigger>
	                          <TooltipContent>
	                            <p>{isSaved ? "Saved" : "Save job"}</p>
	                          </TooltipContent>
	                        </Tooltip>
	                      </TooltipProvider>
	                      {job.is_expired && (
	                        <Badge className="align-middle bg-red-500 text-white hover:bg-red-600">
	                          Expired
	                        </Badge>
	                      )}
	                    </span>
	                  </h1>
	                </div>
	                <JobSourceCompanyLine
	                  source={job.source}
	                  companyName={job.company_name}
                  advertiserName={job.advertiser_name}
                  className="mb-4 text-lg"
                />
              </div>

              <JobAttributeList
                job={job}
                className="mt-2 text-sm text-slate-600"
                showCategory={false}
                showSalary
              />

              <div className="mt-6 flex flex-wrap gap-2">
                {categoryText && (
                  <span className="text-xs text-slate-500">{categoryText}</span>
                )}
                <span className="text-xs text-slate-400 flex items-center ml-auto whitespace-nowrap">
                  Posted{" "}
                  {job.listed_at
                    ? formatDistanceToNow(new Date(job.listed_at), {
                        addSuffix: true,
                      })
                    : "recently"}
                </span>
              </div>
            </div>

            {/* Job Description */}
            <div className="bg-white p-6 md:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-slate-900">
                  Job Description
                </h2>
                <div className="flex items-center gap-2">
                  <JobLanguageSelect
                    value={language}
                    onValueChange={handleLanguageChange}
                    hasChinese={hasCn}
                  />
                </div>
              </div>

              <JobDescriptionHtml html={descriptionHtml} />
            </div>
          </div>

          {/* Sidebar */}
          <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
            <Card>
              <CardContent className="p-6 space-y-4">
                <h3 className="font-semibold text-slate-900">Operations</h3>

                {!isApplicationLoading && !application && (
                  <Button
                    size="sm"
                    onClick={() => setIsApplicationDialogOpen(true)}
                    className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add to Applications
                  </Button>
                )}

                {!isApplicationLoading && application && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Link
                          to={`/applications/${application.id}`}
                          aria-label={`Open application (${applicationStatusPresentation?.label})`}
                          className={cn(
                            "inline-flex w-full items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                            "hover:brightness-95",
                            applicationStatusPresentation?.className,
                            applicationStatusPresentation?.variant === "secondary" &&
                              "border-transparent bg-secondary text-secondary-foreground",
                            applicationStatusPresentation?.variant === "outline" &&
                              "text-foreground",
                            applicationStatusPresentation?.variant == null &&
                              "border-transparent bg-primary text-primary-foreground",
                          )}
                        >
                          <span>{applicationStatusPresentation?.label}</span>
                          <span aria-hidden="true" className="h-4 w-px bg-current/20" />
                          <Eye className="h-4 w-4" />
                        </Link>
                      </TooltipTrigger>
                      <TooltipContent>
                        <div className="max-w-xs">
                          <p className="text-sm font-medium">Open application</p>
                        </div>
                        {application.status === "Failed" &&
                          application.last_error && (
                            <div className="max-w-xs">
                              <p className="font-semibold text-red-500">Error:</p>
                              <p className="text-sm">{application.last_error}</p>
                            </div>
                          )}
                        {application.status === "Tailoring" && (
                          <div className="max-w-xs">
                            <p className="text-sm">
                              Customizing your resume and generating cover
                              letter...
                            </p>
                          </div>
                        )}
                        {application.status === "Pending" && (
                          <div className="max-w-xs">
                            <p className="text-sm">
                              Waiting to start processing...
                            </p>
                          </div>
                        )}
                        {application.status === "Ready" && (
                          <div className="max-w-xs">
                            <p className="text-sm">
                              Application materials are ready!
                            </p>
                          </div>
                        )}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}

	                <Button
	                  variant="outline"
	                  size="sm"
                  onClick={handleToggleExpiration}
                  disabled={setJobExpiration.isPending}
                  className={cn(
                    "w-full",
                    job.manual_expired
                      ? "border-emerald-200 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
                      : "border-red-200 text-red-700 hover:bg-red-50 hover:text-red-800",
                  )}
                >
                  {job.manual_expired ? "Mark as Active" : "Mark as Expired"}
                </Button>
              </CardContent>
            </Card>

            {/* Company Info Card (Placeholder) */}
            <Card>
              <CardContent className="p-6">
                <h3 className="font-semibold text-slate-900 mb-4">
                  About the Company
                </h3>
                <p className="text-sm text-slate-600 mb-4">
                  {job.classification
                    ? `${getCompanyDisplayName(job.company_name, job.advertiser_name)} is a leading company in the ${job.classification} sector.`
                    : `${getCompanyDisplayName(job.company_name, job.advertiser_name)} is a leading company.`}
                </p>
                <Button variant="outline" className="w-full">
                  View Company Profile
                </Button>
              </CardContent>
            </Card>

            {/* AI Insight Card */}
            {job.analysis && (
              <Card>
                <CardContent className="p-6 space-y-6">
                  <h3 className="font-semibold text-slate-900 mb-4">
                    AI Insight
                  </h3>

                  {job.analysis.hiring_priorities.length > 0 && (
                    <div className="bg-indigo-50/50 rounded-lg p-4 border border-indigo-100">
                      <h4 className="flex items-center gap-2 font-semibold text-slate-900 mb-3 text-sm">
                        <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                        Key Hiring Priorities
                      </h4>
                      <div className="space-y-2">
                        {job.analysis.hiring_priorities.map((priority, i) => (
                          <div
                            key={i}
                            className="flex gap-2.5 items-start text-sm text-slate-700"
                          >
                            <div className="mt-1 h-1.5 w-1.5 rounded-full bg-indigo-400 shrink-0" />
                            <span>{priority}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {job.analysis.tech_stack.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="flex items-center gap-2 font-semibold text-slate-900 text-sm">
                        <Code2 className="h-4 w-4 text-indigo-600" />
                        Tech Stack
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {job.analysis.tech_stack.map((tech, i) => (
                          <Badge
                            key={i}
                            variant="secondary"
                            className="bg-slate-100 text-slate-700 hover:bg-slate-200 border-slate-200"
                          >
                            {tech}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {job.analysis.required_skills.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="flex items-center gap-2 font-semibold text-slate-900 text-sm">
                        <Zap className="h-4 w-4 text-indigo-600" />
                        Required Skills
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {job.analysis.required_skills.map((skill, i) => (
                          <Badge
                            key={i}
                            variant="outline"
                            className="text-slate-600 border-slate-200"
                          >
                            {skill}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {(job.analysis.company_culture_keywords.length > 0 ||
                    job.analysis.soft_skills.length > 0) && (
                    <div className="pt-4 border-t border-slate-100">
                      <h4 className="flex items-center gap-2 font-semibold text-slate-900 text-sm mb-3">
                        <Users className="h-4 w-4 text-indigo-600" />
                        Culture & Capabilities
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {job.analysis.company_culture_keywords.map(
                          (culture, i) => (
                            <Badge
                              key={`culture-${i}`}
                              className="bg-purple-50 text-purple-700 hover:bg-purple-100 border-purple-100"
                            >
                              {culture}
                            </Badge>
                          )
                        )}
                        {job.analysis.soft_skills.map((soft, i) => (
                          <Badge
                            key={`soft-${i}`}
                            variant="secondary"
                            className="bg-slate-50 text-slate-600"
                          >
                            {soft}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            <Card>
              <CardContent className="p-6">
                <h3 className="font-semibold text-slate-900 mb-4">Similar Jobs</h3>

                {isSimilarJobsLoading && (
                  <div className="space-y-3">
                    <Skeleton className="h-24 w-full" />
                    <Skeleton className="h-24 w-full" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                )}

                {!isSimilarJobsLoading && (!similarJobs || similarJobs.length === 0) && (
                  <p className="text-sm text-slate-500">No similar jobs found.</p>
                )}

                {!isSimilarJobsLoading && similarJobs && similarJobs.length > 0 && (
                  <div className="space-y-4">
                    {similarJobs.map((similarJob) => (
                      <div
                        key={similarJob.id}
                        className="border border-slate-200 rounded-lg p-4 hover:border-indigo-200 transition-colors"
                      >
                        <Link
                          to={`/jobs/${similarJob.id}?${searchParams.toString()}`}
                          className="font-semibold text-slate-900 hover:text-indigo-600 line-clamp-2"
                        >
                          {similarJob.title}
                        </Link>
                        <div className="mt-2 text-sm text-slate-600 space-y-1">
                          <div className="flex items-center gap-1.5">
                            <Building2 className="h-3.5 w-3.5 text-slate-400" />
                            <span>{getCompanyDisplayName(similarJob.company_name, similarJob.advertiser_name)}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <MapPin className="h-3.5 w-3.5 text-slate-400" />
                            <span>{similarJob.location_label || "Location not specified"}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Clock className="h-3.5 w-3.5 text-slate-400" />
                            <span>
                              {similarJob.listed_at
                                ? formatDistanceToNow(new Date(similarJob.listed_at), {
                                    addSuffix: true,
                                  })
                                : "recently"}
                            </span>
                          </div>
                        </div>
                        {/* <div className="mt-3 flex flex-wrap gap-2">
                          {hasSameCompany(
                            job.company_name,
                            job.advertiser_name,
                            similarJob.company_name,
                            similarJob.advertiser_name,
                          ) && (
                            <Badge variant="secondary" className="text-xs">
                              Same company
                            </Badge>
                          )}
                          {hasSameClassification(job.classification, similarJob.classification) && (
                            <Badge variant="outline" className="text-xs">
                              Same classification
                            </Badge>
                          )}
                        </div> */}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      </main>
    </div>
  );
}


