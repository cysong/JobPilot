/**
 * React Query hooks for Jobs
 */
import { useQuery } from '@tanstack/react-query'
import { jobsApi } from '@/api/jobs'
import type { JobFiltersRequest, JobMatchFiltersRequest } from '@/types/job'

/**
 * Hook to fetch paginated job list with filters
 */
export const useJobs = (filters: JobFiltersRequest) => {
  return useQuery({
    queryKey: ['jobs', filters],
    queryFn: () => jobsApi.getJobs(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Hook to fetch job details by ID
 */
export const useJobDetail = (jobId: number | null) => {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.getJobById(jobId!),
    enabled: !!jobId, // Only run query if jobId is provided
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

/**
 * Hook to fetch similar jobs
 */
export const useSimilarJobs = (jobId: number | null, limit = 5) => {
  return useQuery({
    queryKey: ['similar-jobs', jobId, limit],
    queryFn: () => jobsApi.getSimilarJobs(jobId!, limit),
    enabled: !!jobId,
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

/**
 * Hook to fetch filter options
 */
export const useJobFilterOptions = () => {
  return useQuery({
    queryKey: ['job-filter-options'],
    queryFn: () => jobsApi.getFilterOptions(),
    staleTime: 1000 * 60 * 30, // 30 minutes (filter options don't change often)
  })
}

/**
 * Hook to fetch matched jobs for current user
 */
export const useJobMatches = (filters: JobMatchFiltersRequest) => {
  return useQuery({
    queryKey: ['job-matches', filters],
    queryFn: () => jobsApi.getJobMatches(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}
