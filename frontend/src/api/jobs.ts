/**
 * Job API client
 */
import apiClient from './client'
import type {
  Job,
  JobDetail,
  JobListResponse,
  JobFiltersRequest,
  JobFiltersOptions
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

    // Add date range filters
    if (filters.listed_after) {
      params.append('listed_after', filters.listed_after)
    }
    if (filters.listed_before) {
      params.append('listed_before', filters.listed_before)
    }

    const response = await apiClient.get<JobListResponse>(`/jobs?${params.toString()}`)
    return response.data
  },

  /**
   * Get job details by ID
   */
  getJobById: async (jobId: number): Promise<JobDetail> => {
    const response = await apiClient.get<JobDetail>(`/jobs/${jobId}`)
    return response.data
  },

  /**
   * Get similar jobs (same company and classification)
   */
  getSimilarJobs: async (jobId: number, limit = 5): Promise<Job[]> => {
    const response = await apiClient.get<Job[]>(`/jobs/${jobId}/similar?limit=${limit}`)
    return response.data
  },

  /**
   * Get available filter options for UI dropdowns
   */
  getFilterOptions: async (): Promise<JobFiltersOptions> => {
    const response = await apiClient.get<JobFiltersOptions>('/jobs/filters')
    return response.data
  }
}
