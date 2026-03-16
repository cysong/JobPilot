/**
 * React Query hooks for Jobs
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '@/api/jobs'
import type {
  Job,
  JobFiltersRequest,
  JobMatchFiltersRequest,
  SavedJobListResponse,
  SavedJobStatusResponse,
  JobViewedStatusResponse,
  SavedJobsRequest,
  JobExpirationStatusResponse,
} from '@/types/job'
import { useToast } from '@/components/ui/use-toast'

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
 * Hook to search company options for company filter
 */
export const useCompanyFilterOptions = (keyword: string, limit = 20, enabled = true) => {
  return useQuery({
    queryKey: ['job-company-filter-options', keyword, limit],
    queryFn: () => jobsApi.searchCompanies(keyword, limit),
    enabled: enabled && keyword.trim().length > 0,
    staleTime: 1000 * 60 * 5,
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

/**
 * Hook to fetch current user's saved status for a job
 */
export const useJobSavedStatus = (jobId: number | null) => {
  return useQuery({
    queryKey: ['job-saved-status', jobId],
    queryFn: () => jobsApi.getSavedStatus(jobId!),
    enabled: !!jobId,
  })
}

/**
 * Hook to fetch current user's viewed status for a job
 */
export const useJobViewedStatus = (jobId: number | null) => {
  return useQuery({
    queryKey: ['job-viewed-status', jobId],
    queryFn: () => jobsApi.getViewedStatus(jobId!),
    enabled: !!jobId,
  })
}

/**
 * Hook to fetch current user's saved jobs
 */
export const useSavedJobs = (filters: SavedJobsRequest) => {
  return useQuery({
    queryKey: ['saved-jobs', filters],
    queryFn: () => jobsApi.getSavedJobs(filters),
  })
}

/**
 * Save/unsave mutations for jobs
 */
export const useJobSavedMutations = () => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  type SavedMutationPayload = { jobId: number; job?: Job }
  type SavedListSnapshot = [readonly unknown[], SavedJobListResponse | undefined]

  const recalcTotalPages = (total: number, pageSize: number): number =>
    pageSize > 0 ? Math.ceil(total / pageSize) : 0

  const saveJob = useMutation({
    mutationFn: ({ jobId }: SavedMutationPayload) => jobsApi.saveJob(jobId),
    onMutate: async ({ jobId, job }) => {
      await queryClient.cancelQueries({ queryKey: ['job-saved-status', jobId] })
      await queryClient.cancelQueries({ queryKey: ['saved-jobs'] })

      const previousStatus = queryClient.getQueryData<SavedJobStatusResponse>(['job-saved-status', jobId])
      const previousSavedLists = queryClient.getQueriesData<SavedJobListResponse>({
        queryKey: ['saved-jobs'],
      }) as SavedListSnapshot[]
      const savedAt = new Date().toISOString()

      queryClient.setQueryData<SavedJobStatusResponse>(['job-saved-status', jobId], {
        is_saved: true,
        saved_at: savedAt,
      })

      previousSavedLists.forEach(([queryKey, data]) => {
        if (!data) return

        const filters = queryKey[1] as SavedJobsRequest | undefined
        const page = filters?.page ?? data.page
        const pageSize = filters?.page_size ?? data.page_size

        const hasExisting = data.items.some((item) => item.job.id === jobId)
        let nextItems = data.items
        if (!hasExisting && page === 1 && job) {
          nextItems = [{ job, saved_at: savedAt }, ...data.items].slice(0, pageSize)
        }

        const nextTotal = hasExisting ? data.total : data.total + 1
        queryClient.setQueryData<SavedJobListResponse>(queryKey, {
          ...data,
          items: nextItems,
          total: nextTotal,
          total_pages: recalcTotalPages(nextTotal, pageSize),
        })
      })

      return { previousStatus, previousSavedLists, jobId }
    },
    onError: (_error, _variables, context) => {
      if (!context) return
      queryClient.setQueryData(['job-saved-status', context.jobId], context.previousStatus)
      context.previousSavedLists.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data)
      })
    },
    onSuccess: (_, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: ['job-saved-status', jobId] })
      queryClient.invalidateQueries({ queryKey: ['saved-jobs'] })
      toast({ title: 'Saved', description: 'Job added to saved list' })
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({ queryKey: ['job-saved-status', variables.jobId] })
      queryClient.invalidateQueries({ queryKey: ['saved-jobs'] })
    },
  })

  const unsaveJob = useMutation({
    mutationFn: ({ jobId }: SavedMutationPayload) => jobsApi.unsaveJob(jobId),
    onMutate: async ({ jobId }) => {
      await queryClient.cancelQueries({ queryKey: ['job-saved-status', jobId] })
      await queryClient.cancelQueries({ queryKey: ['saved-jobs'] })

      const previousStatus = queryClient.getQueryData<SavedJobStatusResponse>(['job-saved-status', jobId])
      const previousSavedLists = queryClient.getQueriesData<SavedJobListResponse>({
        queryKey: ['saved-jobs'],
      }) as SavedListSnapshot[]

      queryClient.setQueryData<SavedJobStatusResponse>(['job-saved-status', jobId], {
        is_saved: false,
        saved_at: null,
      })

      previousSavedLists.forEach(([queryKey, data]) => {
        if (!data) return

        const filters = queryKey[1] as SavedJobsRequest | undefined
        const pageSize = filters?.page_size ?? data.page_size
        const hadItem = data.items.some((item) => item.job.id === jobId)
        const nextItems = data.items.filter((item) => item.job.id !== jobId)
        const nextTotal = hadItem ? Math.max(0, data.total - 1) : data.total

        queryClient.setQueryData<SavedJobListResponse>(queryKey, {
          ...data,
          items: nextItems,
          total: nextTotal,
          total_pages: recalcTotalPages(nextTotal, pageSize),
        })
      })

      return { previousStatus, previousSavedLists, jobId }
    },
    onError: (_error, _variables, context) => {
      if (!context) return
      queryClient.setQueryData(['job-saved-status', context.jobId], context.previousStatus)
      context.previousSavedLists.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data)
      })
    },
    onSuccess: (_, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: ['job-saved-status', jobId] })
      queryClient.invalidateQueries({ queryKey: ['saved-jobs'] })
      toast({ title: 'Removed', description: 'Job removed from saved list' })
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({ queryKey: ['job-saved-status', variables.jobId] })
      queryClient.invalidateQueries({ queryKey: ['saved-jobs'] })
    },
  })

  return {
    saveJob,
    unsaveJob,
  }
}

/**
 * Viewed-state mutation for jobs.
 * Intentionally no toast to keep browsing flow uninterrupted.
 */
export const useJobViewedMutations = () => {
  const queryClient = useQueryClient()

  const markViewed = useMutation({
    mutationFn: ({ jobId }: { jobId: number }) => jobsApi.markJobViewed(jobId),
    onMutate: async ({ jobId }) => {
      const now = new Date().toISOString()
      const previousViewed = queryClient.getQueryData<JobViewedStatusResponse>(['job-viewed-status', jobId])
      queryClient.setQueryData<JobViewedStatusResponse>(['job-viewed-status', jobId], {
        is_viewed: true,
        first_viewed_at: previousViewed?.first_viewed_at || now,
        last_viewed_at: now,
        view_count: (previousViewed?.view_count || 0) + 1,
      })

      const patchJob = <T extends { id: number; is_viewed?: boolean; last_viewed_at?: string | null }>(job: T): T => {
        if (job.id !== jobId) return job
        return { ...job, is_viewed: true, last_viewed_at: now }
      }

      queryClient.setQueriesData({ queryKey: ['jobs'] }, (oldData: unknown) => {
        const data = oldData as { items?: Array<{ id: number; is_viewed?: boolean; last_viewed_at?: string | null }> } | undefined
        if (!data?.items) return oldData
        return {
          ...data,
          items: data.items.map((job) => patchJob(job)),
        }
      })

      queryClient.setQueriesData({ queryKey: ['saved-jobs'] }, (oldData: unknown) => {
        const data = oldData as {
          items?: Array<{ job: { id: number; is_viewed?: boolean; last_viewed_at?: string | null } }>
        } | undefined
        if (!data?.items) return oldData
        return {
          ...data,
          items: data.items.map((item) => ({
            ...item,
            job: patchJob(item.job),
          })),
        }
      })

      queryClient.setQueriesData({ queryKey: ['job-matches'] }, (oldData: unknown) => {
        const data = oldData as Array<{ job: { id: number; is_viewed?: boolean; last_viewed_at?: string | null } }> | undefined
        if (!data) return oldData
        return data.map((item) => ({
          ...item,
          job: patchJob(item.job),
        }))
      })
    },
    onSuccess: (data, { jobId }) => {
      queryClient.setQueryData<JobViewedStatusResponse>(['job-viewed-status', jobId], data)
    },
  })

  return { markViewed }
}

/**
 * Manual expired-state mutation for jobs.
 */
export const useJobExpirationMutations = () => {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const setJobExpiration = useMutation({
    mutationFn: ({ jobId, manualExpired, note }: { jobId: number; manualExpired: boolean; note?: string }) =>
      jobsApi.setJobExpiration(jobId, { manual_expired: manualExpired, note }),
    onSuccess: (data: JobExpirationStatusResponse, variables) => {
      queryClient.invalidateQueries({ queryKey: ['job', variables.jobId] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['saved-jobs'] })
      queryClient.invalidateQueries({ queryKey: ['job-matches'] })
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      queryClient.invalidateQueries({ queryKey: ['application', 'by-job', variables.jobId] })

      toast({
        title: 'Success',
        description: data.manual_expired ? 'Job marked as expired' : 'Job marked as active',
      })
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to update job expiration status',
        variant: 'destructive',
      })
    },
  })

  return { setJobExpiration }
}
