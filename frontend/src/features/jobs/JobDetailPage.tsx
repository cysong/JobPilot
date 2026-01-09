import { useEffect, useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import {
  Building2,
  MapPin,
  Clock,
  ArrowLeft,
  Share2,
  ExternalLink,
  Plus,
  Eye,
  BrainCircuit,
  CheckCircle2,
  ListChecks,
  Star,
  Users,
  Code2,
  Zap,
} from "lucide-react";

import { useJobDetail } from "@/features/jobs/hooks/useJobs";
import { useApplicationByJob } from "@/features/applications/hooks/useApplicationByJob";
import { ApplicationDialog } from "@/features/applications/components/ApplicationDialog";
import { ApplicationStatusBadge } from "@/features/applications/components/ApplicationStatusBadge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

const LANGUAGE_STORAGE_KEY = "job_detail_language";

export default function JobDetailPage() {
  const { jobId } = useParams();
  const [searchParams] = useSearchParams();
  const [isApplicationDialogOpen, setIsApplicationDialogOpen] = useState(false);
  const [language, setLanguage] = useState<"en" | "zh">("en");
  const jobIdNum = parseInt(jobId || "0");
  const {
    data: job,
    isLoading,
    isError,
  } = useJobDetail(jobIdNum);

  const hasCn = Boolean(job?.content_cn?.trim() || job?.analysis?.cn_content?.trim());

  useEffect(() => {
    const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (storedLanguage === "zh" && hasCn) {
      setLanguage("zh");
      return;
    }
    setLanguage("en");
  }, [jobIdNum, hasCn]);

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
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                <Share2 className="h-4 w-4 mr-2" />
                Share
              </Button>

              {/* Application Button Logic */}
              {!isApplicationLoading && !application && (
                <Button
                  size="sm"
                  onClick={() => setIsApplicationDialogOpen(true)}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add to Applications
                </Button>
              )}

              {!isApplicationLoading && application && (
                <TooltipProvider>
                  <div className="flex gap-2 items-center">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div>
                          <ApplicationStatusBadge status={application.status} />
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>
                        {application.status === "Failed" && application.last_error && (
                          <div className="max-w-xs">
                            <p className="font-semibold text-red-500">Error:</p>
                            <p className="text-sm">{application.last_error}</p>
                          </div>
                        )}
                        {application.status === "Tailoring" && (
                          <div className="max-w-xs">
                            <p className="text-sm">Customizing your resume and generating cover letter...</p>
                          </div>
                        )}
                        {application.status === "Pending" && (
                          <div className="max-w-xs">
                            <p className="text-sm">Waiting to start processing...</p>
                          </div>
                        )}
                        {application.status === "Ready" && (
                          <div className="max-w-xs">
                            <p className="text-sm">Application materials are ready!</p>
                          </div>
                        )}
                      </TooltipContent>
                    </Tooltip>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                      asChild
                    >
                      <Link to={`/applications/${application.id}`}>
                        <Eye className="h-4 w-4 mr-2" />
                        View Application
                      </Link>
                    </Button>
                  </div>
                </TooltipProvider>
              )}

              {job.share_link && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                  asChild
                >
                  <a
                    href={job.share_link}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View on Seek
                    <ExternalLink className="h-4 w-4 ml-2" />
                  </a>
                </Button>
              )}
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
                <h1 className="text-2xl font-bold text-slate-900 mb-2">
                  {job.title}
                </h1>
                <div className="flex items-center gap-2 text-slate-600 mb-4">
                  <Building2 className="h-5 w-5 text-indigo-600" />
                  <span className="font-medium text-lg">
                    {job.advertiser_name}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap gap-y-2 gap-x-6 text-sm text-slate-600 mt-2 pr-28">
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
                    <span>{job.salary_label}</span>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2 mt-6 pr-28">
                <Badge variant="secondary">{job.classification}</Badge>
                {job.sub_classification && (
                  <Badge variant="outline">{job.sub_classification}</Badge>
                )}
                <span className="text-xs text-slate-400 flex items-center ml-auto">
                  Posted{" "}
                  {job.listed_at
                    ? formatDistanceToNow(new Date(job.listed_at), {
                      addSuffix: true,
                    })
                    : "recently"}
                </span>
              </div>
            </div>

            {/* AI Analysis Card */}
            {job.analysis && (
              <div className="bg-white p-6 rounded-xl border border-indigo-100 shadow-sm space-y-6 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-5">
                  <BrainCircuit className="h-32 w-32 text-indigo-600" />
                </div>

                <div className="flex items-center gap-3 relative">
                  <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-600">
                    <BrainCircuit className="h-6 w-6" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-slate-900">AI Insight</h2>
                    <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
                      Powered by JobPilot AI
                    </p>
                  </div>
                </div>

                <div className="grid gap-6 relative">
                  {/* Hiring Priorities */}
                  {job.analysis.hiring_priorities.length > 0 && (
                    <div className="bg-indigo-50/50 rounded-lg p-4 border border-indigo-100">
                      <h3 className="flex items-center gap-2 font-semibold text-slate-900 mb-3 text-sm">
                        <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                        Key Hiring Priorities
                      </h3>
                      <div className="space-y-2">
                        {job.analysis.hiring_priorities.map((priority, i) => (
                          <div key={i} className="flex gap-2.5 items-start text-sm text-slate-700">
                            <div className="mt-1 h-1.5 w-1.5 rounded-full bg-indigo-400 shrink-0" />
                            <span>{priority}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid md:grid-cols-2 gap-6">
                    {/* Responsibilities */}
                    <div className="space-y-3">
                      <h3 className="flex items-center gap-2 font-semibold text-slate-900 text-sm">
                        <ListChecks className="h-4 w-4 text-indigo-600" />
                        Core Responsibilities
                      </h3>
                      <ul className="space-y-2">
                        {job.analysis.key_responsibilities.slice(0, 5).map((resp, i) => (
                          <li key={i} className="flex gap-2 items-start text-sm text-slate-600">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
                            <span className="line-clamp-2">{resp}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Tech Stack & Skills */}
                    <div className="space-y-4">
                      {job.analysis.tech_stack.length > 0 && (
                        <div className="space-y-2">
                          <h3 className="flex items-center gap-2 font-semibold text-slate-900 text-sm">
                            <Code2 className="h-4 w-4 text-indigo-600" />
                            Tech Stack
                          </h3>
                          <div className="flex flex-wrap gap-1.5">
                            {job.analysis.tech_stack.map((tech, i) => (
                              <Badge key={i} variant="secondary" className="bg-slate-100 text-slate-700 hover:bg-slate-200 border-slate-200">
                                {tech}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {job.analysis.required_skills.length > 0 && (
                        <div className="space-y-2">
                          <h3 className="flex items-center gap-2 font-semibold text-slate-900 text-sm">
                            <Zap className="h-4 w-4 text-indigo-600" />
                            Required Skills
                          </h3>
                          <div className="flex flex-wrap gap-1.5">
                            {job.analysis.required_skills.map((skill, i) => (
                              <Badge key={i} variant="outline" className="text-slate-600 border-slate-200">
                                {skill}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Culture & Soft Skills */}
                  {(job.analysis.company_culture_keywords.length > 0 || job.analysis.soft_skills.length > 0) && (
                    <div className="pt-4 border-t border-slate-100">
                      <h3 className="flex items-center gap-2 font-semibold text-slate-900 text-sm mb-3">
                        <Users className="h-4 w-4 text-indigo-600" />
                        Culture & Capabilities
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {job.analysis.company_culture_keywords.map((culture, i) => (
                          <Badge key={`culture-${i}`} className="bg-purple-50 text-purple-700 hover:bg-purple-100 border-purple-100">
                            {culture}
                          </Badge>
                        ))}
                        {job.analysis.soft_skills.map((soft, i) => (
                          <Badge key={`soft-${i}`} variant="secondary" className="bg-slate-50 text-slate-600">
                            {soft}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Job Description */}
            <div className="bg-white p-6 md:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-slate-900">Job Description</h2>
                <div className="flex items-center gap-2">
                  <Select value={language} onValueChange={handleLanguageChange}>
                    <SelectTrigger className="h-9 w-[140px]">
                      <SelectValue placeholder="Language" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="zh" disabled={!hasCn}>
                        {"\u4e2d\u6587"}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  {!hasCn && (
                    <span className="text-xs text-slate-500">Chinese not available</span>
                  )}
                </div>
              </div>

              <div
                className="prose prose-slate max-w-none 
                  prose-headings:font-bold prose-headings:text-slate-900 prose-headings:mb-3 prose-headings:mt-8 first:prose-headings:mt-0 prose-headings:tracking-tight
                  prose-h3:text-lg 
                  prose-p:text-slate-700 prose-p:leading-relaxed prose-p:mb-4
                  prose-li:text-slate-700 prose-li:marker:text-slate-500 prose-li:my-0.5
                  [&_li_p]:m-0
                  prose-ul:my-4 prose-ul:mb-6
                  prose-strong:font-bold prose-strong:text-slate-900
                  prose-a:text-indigo-600 prose-a:font-medium prose-a:no-underline hover:prose-a:underline"
                dangerouslySetInnerHTML={{
                  __html: descriptionHtml || "<p>No description available.</p>",
                }}
              />
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Company Info Card (Placeholder) */}
            <Card>
              <CardContent className="p-6">
                <h3 className="font-semibold text-slate-900 mb-4">
                  About the Company
                </h3>
                <p className="text-sm text-slate-600 mb-4">
                  {job.company_name || job.advertiser_name} is a leading company
                  in the {job.classification} sector.
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
  );
}


