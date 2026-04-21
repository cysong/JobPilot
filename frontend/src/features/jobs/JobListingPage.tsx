import { useEffect, useMemo } from "react";
import {
  Sparkles,
  Briefcase,
  ChevronDown,
  ChevronUp,
  X,
  Star,
} from "lucide-react";

import {
  useJobs,
  useJobMatches,
  useJobFilterOptions,
  useSavedJobs,
} from "@/features/jobs/hooks/useJobs";
import { useJobListState, type ViewStatus } from "@/features/jobs/hooks/useJobListState";
import { useJobListReturnRestore } from "@/features/jobs/hooks/useJobListReturnRestore";
import type { JobFiltersRequest } from "@/types/job";
import { JobCard } from "@/features/jobs/components/JobCard";
import { FilterDropdown } from "@/features/jobs/components/FilterDropdown";
import { CompanyFilterDropdown } from "@/features/jobs/components/CompanyFilterDropdown";
import { JobSearch } from "@/features/jobs/components/JobSearch";
import { JobPagination } from "@/features/jobs/components/JobPagination";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getSourceMetaByKey, useSourceMetaStore } from "@/store/sourceMetaStore";

export default function JobListingPage() {
  const {
    showFilters,
    setShowFilters,
    isSearchParamsReady,
    viewMode,
    currentPage,
    viewStatus,
    contextKey,
    keyword,
    sortBy,
    sortOrder,
    locationCities,
    workTypes,
    companies,
    sources,
    hideExpired,
    isRecommendedView,
    isSavedView,
    activeFilterCount,
    handleViewChange,
    handleFilterChange,
    handleViewStatusChange,
    handleHideExpiredChange,
    handleClearAllFilters,
    handleResetAllJobsSearch,
  } = useJobListState();

  // Fetch filter options
  const { data: filterOptions } = useJobFilterOptions();

  // Source meta (label / brand_color) for the Source filter dropdown.
  // Subscribe to `byKey` so the dropdown re-derives once the async fetch
  // resolves, and trigger `fetchIfNeeded` here so labels are available even
  // if the job list is empty (no JobCard mounted yet to warm the cache).
  const sourceMetaByKey = useSourceMetaStore((s) => s.byKey);
  const fetchSourceMeta = useSourceMetaStore((s) => s.fetchIfNeeded);
  useEffect(() => {
    void fetchSourceMeta();
  }, [fetchSourceMeta]);

  const sourceFilterOptions = useMemo(
    () =>
      (filterOptions?.sources ?? []).map((key) => ({
        value: key,
        label: getSourceMetaByKey(key)?.label ?? key,
      })),
    // `sourceMetaByKey` in deps ensures we re-derive labels after the meta
    // fetch resolves; `getSourceMetaByKey` reads the same store snapshot.
    [filterOptions?.sources, sourceMetaByKey],
  );

  // Recommended view: fetch matched jobs
  const matchFilters = {
    min_score: 40, // Only show jobs with skill match >= 70%
    limit: 10,
    offset: (currentPage - 1) * 10,
  };
  const matchesQuery = useJobMatches(matchFilters, isSearchParamsReady && isRecommendedView);
  const savedJobsQuery = useSavedJobs({
    page: currentPage,
    page_size: 10,
  }, isSearchParamsReady && isSavedView);

  // All jobs view: fetch with filters
  const jobFilters: JobFiltersRequest = {
    page: currentPage,
    page_size: 10,
    sort_by: sortBy,
    sort_order: sortOrder,
    keyword,
    location_cities: locationCities,
    work_types: workTypes,
    companies,
    sources,
    view_status: viewStatus,
    hide_expired: hideExpired || undefined,
  };
  const jobsQuery = useJobs(jobFilters, isSearchParamsReady && !isRecommendedView && !isSavedView);

  const {
    data: matchesData,
    isLoading: matchesLoading,
    isError: matchesError,
  } = matchesQuery;
  const {
    data: jobsData,
    isLoading: jobsLoading,
    isError: jobsError,
  } = jobsQuery;
  const {
    data: savedData,
    isLoading: savedLoading,
    isError: savedError,
  } = savedJobsQuery;

  const isLoading = isRecommendedView
    ? matchesLoading
    : isSavedView
      ? savedLoading
      : jobsLoading;
  const isListLoading = !isSearchParamsReady || isLoading;
  const isError = isRecommendedView
    ? matchesError
    : isSavedView
      ? savedError
      : jobsError;

  // Calculate pagination for matches (backend returns array, not paginated response)
  const totalMatches = matchesData?.length || 0;
  const matchesTotal = totalMatches; // We'll use the array length as total
  const matchesTotalPages = Math.ceil(matchesTotal / 10);

  const visibleJobIds = useMemo(() => {
    if (isRecommendedView) {
      return (matchesData || []).map((item) => item.job.id);
    }
    if (isSavedView) {
      return (savedData?.items || []).map((item) => item.job.id);
    }
    return (jobsData?.items || []).map((item) => item.id);
  }, [isRecommendedView, isSavedView, jobsData, matchesData, savedData]);

  const { highlightedJobId, handleOpenJob } = useJobListReturnRestore({
    contextKey,
    isSearchParamsReady,
    isLoading,
    isError,
    itemIds: visibleJobIds,
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header with Tabs and Search */}
      <div className="px-6">
        <div className="bg-white border-b rounded-lg shadow-sm border-slate-200 sticky top-[65px] z-30 px-6 py-4">
          {/* View Mode Tabs - at the top */}
          <div className="">
            <Tabs value={viewMode} onValueChange={handleViewChange}>
              <TabsList className="grid w-full max-w-lg grid-cols-3">
                <TabsTrigger value="recommended" className="gap-2">
                  <Sparkles className="h-4 w-4" />
                  Recommended
                </TabsTrigger>
                <TabsTrigger value="all" className="gap-2">
                  <Briefcase className="h-4 w-4" />
                  All Jobs
                </TabsTrigger>
                <TabsTrigger value="saved" className="gap-2">
                  <Star className="h-4 w-4" />
                  Saved
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {/* Search Bar - only show in 'all' view */}
          {viewMode === "all" && (
            <>
              <div className="flex items-center gap-4 mt-4">
                <div className="flex-1">
                  <JobSearch />
                </div>

                <Tabs
                  value={viewStatus}
                  onValueChange={(value) =>
                    handleViewStatusChange(value as ViewStatus)
                  }
                >
                  <TabsList className="grid grid-cols-3">
                    <TabsTrigger value="all">All</TabsTrigger>
                    <TabsTrigger value="unviewed">Unviewed</TabsTrigger>
                    <TabsTrigger value="viewed">Viewed</TabsTrigger>
                  </TabsList>
                </Tabs>

                {/* Hide Expired Switch */}
                <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-slate-600">
                  <Switch
                    checked={hideExpired}
                    onCheckedChange={handleHideExpiredChange}
                  />
                  Hide expired
                </label>

                {/* Filter Toggle Button */}
                <Button
                  variant="outline"
                  className="gap-2"
                  onClick={() => setShowFilters(!showFilters)}
                >
                  {showFilters ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                  <span className="hidden sm:inline">Filters</span>
                  {activeFilterCount > 0 && (
                    <span className="bg-indigo-600 text-white text-xs rounded-full px-2 py-0.5">
                      {activeFilterCount}
                    </span>
                  )}
                </Button>
              </div>

              {/* Inline Filters - show when toggled or when filters are active */}
              {showFilters && filterOptions && (
                <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
                  <div className="flex flex-wrap items-center gap-3">
                    {/* Filter Dropdowns */}
                    <FilterDropdown
                      label="Source"
                      options={sourceFilterOptions}
                      selectedValues={sources}
                      onSelectionChange={(values) =>
                        handleFilterChange("sources", values)
                      }
                      searchPlaceholder="Search sources..."
                      emptyText="No sources found"
                    />

                    <FilterDropdown
                      label="Location"
                      options={filterOptions.location_cities}
                      selectedValues={locationCities}
                      onSelectionChange={(values) =>
                        handleFilterChange("location_cities", values)
                      }
                      searchPlaceholder="Search locations..."
                      emptyText="No locations found"
                    />

                    <FilterDropdown
                      label="Work Type"
                      options={filterOptions.work_types}
                      selectedValues={workTypes}
                      onSelectionChange={(values) =>
                        handleFilterChange("work_types", values)
                      }
                      searchPlaceholder="Search work types..."
                      emptyText="No work types found"
                    />

                    <CompanyFilterDropdown
                      selectedValues={companies}
                      onSelectionChange={(values) =>
                        handleFilterChange("companies", values)
                      }
                    />

                    {/* Clear All Button */}
                    {activeFilterCount > 0 && (
                      <>
                        <div className="hidden sm:block flex-1" />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={handleClearAllFilters}
                          className="gap-2 text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <X className="h-4 w-4" />
                          Clear All
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="px-6 py-8">
        {/* Job List - Full width */}
        <div className="max-w-7xl mx-auto">
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-slate-900">
                {isListLoading ? (
                  <Skeleton className="h-8 w-32" />
                ) : isRecommendedView ? (
                  `${totalMatches} Matched Jobs`
                ) : isSavedView ? (
                  `${savedData?.total || 0} Saved Jobs`
                ) : (
                  `${jobsData?.total || 0} Jobs Found`
                )}
              </h2>
            </div>

            {isListLoading ? (
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
                        onOpenJob={handleOpenJob}
                        highlighted={highlightedJobId === match.job.id}
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
            ) : isSavedView ? (
              savedData?.items.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                  <p className="text-slate-500">No saved jobs yet.</p>
                </div>
              ) : (
                <>
                  <div className="space-y-4">
                    {savedData?.items.map((item) => (
                      <JobCard
                        key={item.job.id}
                        job={item.job}
                        savedAt={item.saved_at}
                        onOpenJob={handleOpenJob}
                        highlighted={highlightedJobId === item.job.id}
                      />
                    ))}
                  </div>
                  <JobPagination
                    currentPage={savedData?.page || 1}
                    totalPages={savedData?.total_pages || 1}
                  />
                </>
              )
            ) : // All jobs view
            jobsData?.items.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg border border-slate-200">
                <p className="text-slate-500">
                  No jobs found matching your criteria.
                </p>
                <Button
                  variant="link"
                  onClick={handleResetAllJobsSearch}
                  className="mt-2 text-indigo-600"
                >
                  Clear all filters
                </Button>
              </div>
            ) : (
              <>
                <div className="space-y-4">
                  {jobsData?.items.map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      onOpenJob={handleOpenJob}
                      highlighted={highlightedJobId === job.id}
                    />
                  ))}
                </div>
                <JobPagination
                  currentPage={jobsData?.page || 1}
                  totalPages={jobsData?.total_pages || 1}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
