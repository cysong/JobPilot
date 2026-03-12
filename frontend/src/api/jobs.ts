/**
 * Job API client
 */
import apiClient from './client'
import type {
  Job,
  JobDetail,
  JobListResponse,
  JobFiltersRequest,
  JobFiltersOptions,
  UserJobMatch,
  UserJobMatchDetail,
  JobMatchFiltersRequest,
  SavedJobStatusResponse,
  JobViewedStatusResponse,
  SavedJobListResponse,
  SavedJobsRequest,
} from '@/types/job'

export const jobsApi = {
  /**
   * Get paginated job list with filters
   */
  getJobs: async (filters: JobFiltersRequest): Promise<JobListResponse> => {
    const params = new URLSearchParams()

    // Add pagination
    params.append('page', filters.page.toString())
    params.append('page_size', filters.page_size.toString())

    // Add sorting
    params.append('sort_by', filters.sort_by)
    params.append('sort_order', filters.sort_order)

    // Add search keyword
    if (filters.keyword) {
      params.append('keyword', filters.keyword)
    }

    // Add location cities filter
    if (filters.location_cities && filters.location_cities.length > 0) {
      filters.location_cities.forEach(city => {
        params.append('location_cities', city)
      })
    }

    // Add work types filter
    if (filters.work_types && filters.work_types.length > 0) {
      filters.work_types.forEach(type => {
        params.append('work_types', type)
      })
    }

    // Add companies filter
    if (filters.companies && filters.companies.length > 0) {
      filters.companies.forEach(company => {
        params.append('companies', company)
      })
    }

    // Add sources filter
    if (filters.sources && filters.sources.length > 0) {
      filters.sources.forEach(source => {
        params.append('sources', source)
      })
    }

    if (filters.view_status && filters.view_status !== 'all') {
      params.append('view_status', filters.view_status)
    }

    // Add date range filters
    if (filters.listed_after) {
      params.append('listed_after', filters.listed_after)
    }
    if (filters.listed_before) {
      params.append('listed_before', filters.listed_before)
    }

    const result = await apiClient.get<JobListResponse, JobListResponse>(`/jobs?${params.toString()}`)
    return result
  },

  /**
   * Get job details by ID
   */
  getJobById: async (jobId: number): Promise<JobDetail> => {
    const result = await apiClient.get<JobDetail, JobDetail>(`/jobs/${jobId}`)
    return result
  },

  /**
   * Get saved status for current user
   */
  getSavedStatus: async (jobId: number): Promise<SavedJobStatusResponse> => {
    const result = await apiClient.get<SavedJobStatusResponse, SavedJobStatusResponse>(`/jobs/${jobId}/saved`)
    return result
  },

  getViewedStatus: async (jobId: number): Promise<JobViewedStatusResponse> => {
    const result = await apiClient.get<JobViewedStatusResponse, JobViewedStatusResponse>(`/jobs/${jobId}/viewed`)
    return result
  },

  markJobViewed: async (jobId: number): Promise<JobViewedStatusResponse> => {
    const result = await apiClient.post<JobViewedStatusResponse, JobViewedStatusResponse>(`/jobs/${jobId}/viewed`)
    return result
  },

  /**
   * Save a job for current user
   */
  saveJob: async (jobId: number): Promise<SavedJobStatusResponse> => {
    const result = await apiClient.post<SavedJobStatusResponse, SavedJobStatusResponse>(`/jobs/${jobId}/saved`)
    return result
  },

  /**
   * Remove job from saved list for current user
   */
  unsaveJob: async (jobId: number): Promise<SavedJobStatusResponse> => {
    const result = await apiClient.delete<SavedJobStatusResponse, SavedJobStatusResponse>(`/jobs/${jobId}/saved`)
    return result
  },

  /**
   * Get paginated saved jobs for current user
   */
  getSavedJobs: async (params: SavedJobsRequest): Promise<SavedJobListResponse> => {
    const query = new URLSearchParams()
    query.append('page', params.page.toString())
    query.append('page_size', params.page_size.toString())
    const result = await apiClient.get<SavedJobListResponse, SavedJobListResponse>(`/jobs/saved?${query.toString()}`)
    return result
  },

  /**
   * Get similar jobs (same company and classification)
   */
  getSimilarJobs: async (jobId: number, limit = 5): Promise<Job[]> => {
    const result = await apiClient.get<Job[], Job[]>(`/jobs/${jobId}/similar?limit=${limit}`)
    return result
  },

  /**
   * Get available filter options for UI dropdowns
   */
  getFilterOptions: async (): Promise<JobFiltersOptions> => {
    const result = await apiClient.get<JobFiltersOptions, JobFiltersOptions>('/jobs/filters')
    return result
  },

  /**
   * Search company options for filter dropdown
   */
  searchCompanies: async (keyword: string, limit = 20): Promise<string[]> => {
    const params = new URLSearchParams()
    params.append('q', keyword)
    params.append('limit', limit.toString())
    const result = await apiClient.get<string[], string[]>(`/jobs/filters/companies?${params.toString()}`)
    return result
  },

  /**
   * Get matched jobs for current user
   */
  getJobMatches: async (filters: JobMatchFiltersRequest): Promise<UserJobMatch[]> => {
    const params = new URLSearchParams()

    if (filters.min_score !== undefined) {
      params.append('min_score', filters.min_score.toString())
    }
    if (filters.limit !== undefined) {
      params.append('limit', filters.limit.toString())
    }
    if (filters.offset !== undefined) {
      params.append('offset', filters.offset.toString())
    }

    const result = await apiClient.get<UserJobMatch[], UserJobMatch[]>(
      `/jobs/matches?${params.toString()}`
    )
    return result
  },

  /**
   * Get match detail for a specific job
   */
  getJobMatchDetail: async (jobId: number): Promise<UserJobMatchDetail> => {
    const result = await apiClient.get<UserJobMatchDetail, UserJobMatchDetail>(
      `/jobs/matches/${jobId}`
    )
    return result
  },
}
