import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Filter, Sparkles, Briefcase } from "lucide-react";

import { useJobs, useJobMatches } from "@/features/jobs/hooks/useJobs";
import type { JobFiltersRequest } from "@/types/job";
import { JobCard } from "@/features/jobs/components/JobCard";
import { JobFilters } from "@/features/jobs/components/JobFilters";
import { JobSearch } from "@/features/jobs/components/JobSearch";
import { JobPagination } from "@/features/jobs/components/JobPagination";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function JobListingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isMobileFiltersOpen, setIsMobileFiltersOpen] = useState(false);

  // Get view mode from URL (default: recommended)
  const viewMode = searchParams.get("view") || "recommended";
  const currentPage = parseInt(searchParams.get("page") || "1");

  // Recommended view: fetch matched jobs
  const matchFilters = {
    min_score: 40, // Only show jobs with skill match >= 70%
    limit: 10,
    offset: (currentPage - 1) * 10,
  };
  const matchesQuery = useJobMatches(matchFilters);

  // All jobs view: fetch with filters
  const jobFilters: JobFiltersRequest = {
    page: currentPage,
    page_size: 10,
    sort_by: searchParams.get("sort_by") || "listed_at",
    sort_order: (searchParams.get("sort_order") as "asc" | "desc") || "desc",
    keyword: searchParams.get("keyword") || undefined,
    location_cities: searchParams.getAll("location_cities"),
    work_types: searchParams.getAll("work_types"),
    companies: searchParams.getAll("companies"),
  };
  const jobsQuery = useJobs(jobFilters);

  // Select data based on view mode
  const isRecommendedView = viewMode === "recommended";
  const { data: matchesData, isLoading: matchesLoading, isError: matchesError } = matchesQuery;
  const { data: jobsData, isLoading: jobsLoading, isError: jobsError } = jobsQuery;

  const isLoading = isRecommendedView ? matchesLoading : jobsLoading;
  const isError = isRecommendedView ? matchesError : jobsError;

  // Calculate pagination for matches (backend returns array, not paginated response)
  const totalMatches = matchesData?.length || 0;
  const matchesTotal = totalMatches; // We'll use the array length as total
  const matchesTotalPages = Math.ceil(matchesTotal / 10);

  // Handle view mode change
  const handleViewChange = (newView: string) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set("view", newView);
    newParams.set("page", "1"); // Reset to first page
    setSearchParams(newParams);
  };

  // Scroll to top on page change
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [currentPage]);

  return (
    <div className="flex flex-col h-full">
      {/* Header / Search Bar */}
      <div className="px-6">
        <div className="bg-white border-b rounded-lg shadow-sm border-slate-200 sticky top-[65px] z-30 px-6 py-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <JobSearch />
            </div>

            {/* Mobile Filter Toggle - only show in 'all' view */}
            {!isRecommendedView && (
              <Sheet
                open={isMobileFiltersOpen}
                onOpenChange={setIsMobileFiltersOpen}
              >
                <SheetTrigger asChild>
                  <Button variant="outline" size="icon" className="lg:hidden">
                    <Filter className="h-4 w-4" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="w-[300px] sm:w-[400px]">
                  <SheetHeader>
                    <SheetTitle>Filters</SheetTitle>
                  </SheetHeader>
                  <div className="mt-6">
                    <JobFilters />
                  </div>
                </SheetContent>
              </Sheet>
            )}
          </div>

          {/* View Mode Tabs */}
          <div className="mt-4">
            <Tabs value={viewMode} onValueChange={handleViewChange}>
              <TabsList className="grid w-full max-w-md grid-cols-2">
                <TabsTrigger value="recommended" className="gap-2">
                  <Sparkles className="h-4 w-4" />
                  Recommended
                </TabsTrigger>
                <TabsTrigger value="all" className="gap-2">
                  <Briefcase className="h-4 w-4" />
                  All Jobs
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
      </div>

      <div className="px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Desktop Filters Sidebar - only show in 'all' view */}
          {!isRecommendedView && (
            <div className="hidden lg:block lg:col-span-1">
              <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200 sticky top-40">
                <JobFilters />
              </div>
            </div>
          )}

          {/* Job List */}
          <div className={isRecommendedView ? "lg:col-span-4" : "lg:col-span-3"}>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-slate-900">
                {isLoading ? (
                  <Skeleton className="h-8 w-32" />
                ) : isRecommendedView ? (
                  `${totalMatches} Matched Jobs`
                ) : (
                  `${jobsData?.total || 0} Jobs Found`
                )}
              </h2>
            </div>

            {isLoading ? (
              // Loading Skeletons
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="bg-white p-4 rounded-lg border border-slate-200 space-y-3"
                  >
                    <div className="flex justify-between">
                      <div className="space-y-2">
                        <Skeleton className="h-6 w-48" />
                        <Skeleton className="h-4 w-32" />
                      </div>
                      <Skeleton className="h-12 w-12 rounded-md" />
                    </div>
                    <div className="flex gap-2">
                      <Skeleton className="h-4 w-20" />
                      <Skeleton className="h-4 w-20" />
                    </div>
                  </div>
                ))}
              </div>
            ) : isError ? (
              <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                <p className="text-red-500">
                  Failed to load jobs. Please try again.
                </p>
              </div>
            ) : isRecommendedView ? (
              // Recommended view
              matchesData && matchesData.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                  <p className="text-slate-500">
                    No matched jobs found. Try viewing all jobs.
                  </p>
                  <Button
                    variant="link"
                    onClick={() => handleViewChange("all")}
                    className="mt-2 text-indigo-600"
                  >
                    View All Jobs
                  </Button>
                </div>
              ) : (
                <>
                  <div className="space-y-4">
                    {matchesData?.map((match) => (
                      <JobCard
                        key={match.id}
                        job={match.job}
                        matchData={match}
                      />
                    ))}
                  </div>
                  {matchesTotalPages > 1 && (
                    <JobPagination
                      currentPage={currentPage}
                      totalPages={matchesTotalPages}
                    />
                  )}
                </>
              )
            ) : (
              // All jobs view
              jobsData?.items.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                  <p className="text-slate-500">
                    No jobs found matching your criteria.
                  </p>
                  <Button
                    variant="link"
                    onClick={() => (window.location.href = "/jobs")}
                    className="mt-2 text-indigo-600"
                  >
                    Clear all filters
                  </Button>
                </div>
              ) : (
                <>
                  <div className="space-y-4">
                    {jobsData?.items.map((job) => (
                      <JobCard key={job.id} job={job} />
                    ))}
                  </div>
                  <JobPagination
                    currentPage={jobsData?.page || 1}
                    totalPages={jobsData?.total_pages || 1}
                  />
                </>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
