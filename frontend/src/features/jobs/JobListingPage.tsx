import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
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
import type { JobFiltersRequest } from "@/types/job";
import { JobCard } from "@/features/jobs/components/JobCard";
import { FilterDropdown } from "@/features/jobs/components/FilterDropdown";
import { CompanyFilterDropdown } from "@/features/jobs/components/CompanyFilterDropdown";
import { JobSearch } from "@/features/jobs/components/JobSearch";
import { JobPagination } from "@/features/jobs/components/JobPagination";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePersistedListSearchParams } from "@/hooks/usePersistedListSearchParams";
import {
  clearSessionStorageKeys,
  getListContextKey,
  readSessionRecord,
  type ListOrderState,
  type ListPositionState,
  type ListReturnIntent,
  writeSessionRecord,
} from "@/utils/listState";

type ViewStatus = "all" | "viewed" | "unviewed";

const JOB_LIST_POSITIONS_KEY = "jobs:list:positions";
const JOB_LIST_RETURN_INTENT_KEY = "jobs:list:return-intent";
const JOB_LIST_ORDERS_KEY = "jobs:list:orders";
const JOB_LIST_SEARCH_SNAPSHOT_KEY = "jobs:list:search-snapshot";
const RESTORE_HIGHLIGHT_MS = 2000;
const JOB_TRACKED_SEARCH_KEYS = [
  "view",
  "page",
  "keyword",
  "sort_by",
  "sort_order",
  "view_status",
  "location_cities",
  "work_types",
  "companies",
  "sources",
];

const getContextKey = (params: URLSearchParams): string => getListContextKey("jobs:list", params);

export default function JobListingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [showFilters, setShowFilters] = useState(false);
  const [highlightedJobId, setHighlightedJobId] = useState<number | null>(null);
  const previousContextKey = useRef<string | null>(null);
  const { isSearchParamsReady, clearPersistedSearchParams } = usePersistedListSearchParams({
    searchParams,
    setSearchParams,
    storageKey: JOB_LIST_SEARCH_SNAPSHOT_KEY,
    trackedKeys: JOB_TRACKED_SEARCH_KEYS,
  });

  // Get view mode from URL (default: recommended)
  const viewMode = searchParams.get("view") || "recommended";
  const currentPage = parseInt(searchParams.get("page") || "1");
  const viewStatus = (searchParams.get("view_status") as ViewStatus) || "all";
  const contextKey = getContextKey(searchParams);

  // Get active filters
  const locationCities = searchParams.getAll("location_cities");
  const workTypes = searchParams.getAll("work_types");
  const companies = searchParams.getAll("companies");
  const sources = searchParams.getAll("sources");
  const activeFilterCount =
    locationCities.length +
    workTypes.length +
    companies.length +
    sources.length +
    (viewStatus === "all" ? 0 : 1);

  // Fetch filter options
  const { data: filterOptions } = useJobFilterOptions();

  // Track previous filter count to detect 0 -> >0 transition
  const prevFilterCount = useRef(0);

  // Auto-show filters only when transitioning from no filters to having filters
  useEffect(() => {
    // Only auto-show when filters go from 0 to > 0 (first filter added)
    // This allows users to manually hide the panel even when filters are active
    if (prevFilterCount.current === 0 && activeFilterCount > 0) {
      setShowFilters(true);
    }
    prevFilterCount.current = activeFilterCount;
  }, [activeFilterCount]);

  const isRecommendedView = viewMode === "recommended";
  const isSavedView = viewMode === "saved";

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
    sort_by: searchParams.get("sort_by") || "listed_at",
    sort_order: (searchParams.get("sort_order") as "asc" | "desc") || "desc",
    keyword: searchParams.get("keyword") || undefined,
    location_cities: searchParams.getAll("location_cities"),
    work_types: searchParams.getAll("work_types"),
    companies: searchParams.getAll("companies"),
    sources: searchParams.getAll("sources"),
    view_status: viewStatus,
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

  // Handle view mode change
  const handleViewChange = (newView: string) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set("view", newView);
    newParams.set("page", "1"); // Reset to first page
    setSearchParams(newParams);
  };

  // Handle filter selection change
  const handleFilterChange = (
    filterKey: "location_cities" | "work_types" | "companies" | "sources",
    values: string[],
  ) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.delete(filterKey);
    values.forEach((v) => newParams.append(filterKey, v));
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handleViewStatusChange = (nextStatus: ViewStatus) => {
    const newParams = new URLSearchParams(searchParams);
    if (nextStatus === "all") {
      newParams.delete("view_status");
    } else {
      newParams.set("view_status", nextStatus);
    }
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  // Handle clear all filters
  const handleClearAllFilters = () => {
    clearPersistedSearchParams();
    clearSessionStorageKeys([
      JOB_LIST_POSITIONS_KEY,
      JOB_LIST_RETURN_INTENT_KEY,
      JOB_LIST_ORDERS_KEY,
    ]);
    const newParams = new URLSearchParams(searchParams);
    newParams.delete("location_cities");
    newParams.delete("work_types");
    newParams.delete("companies");
    newParams.delete("sources");
    newParams.delete("view_status");
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handleResetAllJobsSearch = () => {
    clearPersistedSearchParams();
    clearSessionStorageKeys([
      JOB_LIST_POSITIONS_KEY,
      JOB_LIST_RETURN_INTENT_KEY,
      JOB_LIST_ORDERS_KEY,
    ]);
    const newParams = new URLSearchParams();
    newParams.set("view", "all");
    newParams.set("page", "1");
    setSearchParams(newParams, { replace: true });
  };

  const handleOpenJob = (jobId: number) => {
    const positions = readSessionRecord<ListPositionState<number>>(JOB_LIST_POSITIONS_KEY);
    positions[contextKey] = {
      anchorItemId: jobId,
      scrollY: window.scrollY,
      updatedAt: Date.now(),
    };
    writeSessionRecord(JOB_LIST_POSITIONS_KEY, positions);
  };

  // Reset to top when list context changes (filters/search/sort/view/page)
  useEffect(() => {
    if (previousContextKey.current && previousContextKey.current !== contextKey) {
      window.scrollTo({ top: 0, behavior: "auto" });
    }
    previousContextKey.current = contextKey;
  }, [contextKey]);

  // Restore anchor position only when returning from detail with same context.
  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return;

    const intentMap = readSessionRecord<ListReturnIntent<number>>(JOB_LIST_RETURN_INTENT_KEY);
    const intent = intentMap.current || null;
    if (!intent || intent.contextKey !== contextKey) {
      return;
    }

    sessionStorage.removeItem(JOB_LIST_RETURN_INTENT_KEY);

    const positions = readSessionRecord<ListPositionState<number>>(JOB_LIST_POSITIONS_KEY);
    const position = positions[contextKey];
    const targetJobId = intent.itemId || position?.anchorItemId;
    if (!targetJobId) return;

    requestAnimationFrame(() => {
      const anchorElement = document.querySelector(`[data-job-id="${targetJobId}"]`);
      if (anchorElement instanceof HTMLElement) {
        anchorElement.scrollIntoView({ block: "center", behavior: "auto" });
      } else if (position?.scrollY !== undefined) {
        window.scrollTo({ top: position.scrollY, behavior: "auto" });
      }
      setHighlightedJobId(targetJobId);
      window.setTimeout(() => setHighlightedJobId(null), RESTORE_HIGHLIGHT_MS);
    });
  }, [contextKey, isError, isLoading, isSearchParamsReady]);

  // Persist job order per context for detail page previous/next navigation.
  useEffect(() => {
    if (!isSearchParamsReady || isLoading || isError) return;

    let jobIds: number[] = [];
    if (isRecommendedView) {
      jobIds = (matchesData || []).map((item) => item.job.id);
    } else if (isSavedView) {
      jobIds = (savedData?.items || []).map((item) => item.job.id);
    } else {
      jobIds = (jobsData?.items || []).map((item) => item.id);
    }

    const orders = readSessionRecord<ListOrderState<number>>(JOB_LIST_ORDERS_KEY);
    orders[contextKey] = {
      itemIds: jobIds,
      updatedAt: Date.now(),
    };
    writeSessionRecord(JOB_LIST_ORDERS_KEY, orders);
  }, [
    contextKey,
    isError,
    isLoading,
    isRecommendedView,
    isSavedView,
    jobsData,
    matchesData,
    savedData,
    isSearchParamsReady,
  ]);

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
                      options={filterOptions.sources}
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
