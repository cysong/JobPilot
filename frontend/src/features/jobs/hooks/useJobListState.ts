import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { usePersistedListSearchParams } from "@/hooks/usePersistedListSearchParams";
import { clearSessionStorageKeys, getListContextKey } from "@/utils/listState";
import {
  cloneSearchParams,
  replaceMultiValueSearchParam,
  setOptionalSearchParam,
} from "@/utils/searchParams";

export type ViewStatus = "all" | "viewed" | "unviewed";

const JOB_LIST_POSITIONS_KEY = "jobs:list:positions";
const JOB_LIST_RETURN_INTENT_KEY = "jobs:list:return-intent";
const JOB_LIST_ORDERS_KEY = "jobs:list:orders";
const JOB_LIST_SEARCH_SNAPSHOT_KEY = "jobs:list:search-snapshot";
const JOB_TRACKED_SEARCH_KEYS = [
  "view",
  "page",
  "keyword",
  "sort_by",
  "sort_order",
  "view_status",
  "hide_expired",
  "location_cities",
  "work_types",
  "companies",
  "sources",
];

const clearJobListSessionState = () => {
  clearSessionStorageKeys([
    JOB_LIST_POSITIONS_KEY,
    JOB_LIST_RETURN_INTENT_KEY,
    JOB_LIST_ORDERS_KEY,
  ]);
};

export const useJobListState = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [showFilters, setShowFilters] = useState(false);
  const { isSearchParamsReady, clearPersistedSearchParams } = usePersistedListSearchParams({
    searchParams,
    setSearchParams,
    storageKey: JOB_LIST_SEARCH_SNAPSHOT_KEY,
    trackedKeys: JOB_TRACKED_SEARCH_KEYS,
  });

  const viewMode = searchParams.get("view") || "recommended";
  const currentPage = parseInt(searchParams.get("page") || "1");
  const viewStatus = (searchParams.get("view_status") as ViewStatus) || "all";
  const contextKey = getListContextKey("jobs:list", searchParams);
  const keyword = searchParams.get("keyword") || undefined;
  const sortBy = searchParams.get("sort_by") || "listed_at";
  const sortOrder = (searchParams.get("sort_order") as "asc" | "desc") || "desc";
  const locationCities = searchParams.getAll("location_cities");
  const workTypes = searchParams.getAll("work_types");
  const companies = searchParams.getAll("companies");
  const sources = searchParams.getAll("sources");
  const hideExpired = searchParams.get("hide_expired") === "true";
  const isRecommendedView = viewMode === "recommended";
  const isSavedView = viewMode === "saved";
  const activeFilterCount =
    locationCities.length +
    workTypes.length +
    companies.length +
    sources.length +
    (viewStatus === "all" ? 0 : 1);

  const prevFilterCount = useRef(0);
  useEffect(() => {
    if (prevFilterCount.current === 0 && activeFilterCount > 0) {
      setShowFilters(true);
    }
    prevFilterCount.current = activeFilterCount;
  }, [activeFilterCount]);

  const handleViewChange = (newView: string) => {
    const newParams = cloneSearchParams(searchParams);
    newParams.set("view", newView);
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handleFilterChange = (
    filterKey: "location_cities" | "work_types" | "companies" | "sources",
    values: string[],
  ) => {
    const newParams = cloneSearchParams(searchParams);
    replaceMultiValueSearchParam(newParams, filterKey, values);
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handleViewStatusChange = (nextStatus: ViewStatus) => {
    const newParams = cloneSearchParams(searchParams);
    setOptionalSearchParam(newParams, "view_status", nextStatus === "all" ? null : nextStatus);
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handleHideExpiredChange = (value: boolean) => {
    const newParams = cloneSearchParams(searchParams);
    if (value) {
      newParams.set("hide_expired", "true");
    } else {
      newParams.delete("hide_expired");
    }
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handleClearAllFilters = () => {
    clearPersistedSearchParams();
    clearJobListSessionState();
    const newParams = cloneSearchParams(searchParams);
    newParams.delete("location_cities");
    newParams.delete("work_types");
    newParams.delete("companies");
    newParams.delete("sources");
    newParams.delete("view_status");
    newParams.delete("hide_expired");
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handleResetAllJobsSearch = () => {
    clearPersistedSearchParams();
    clearJobListSessionState();
    const newParams = new URLSearchParams();
    newParams.set("view", "all");
    newParams.set("page", "1");
    setSearchParams(newParams, { replace: true });
  };

  return {
    searchParams,
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
  };
};
