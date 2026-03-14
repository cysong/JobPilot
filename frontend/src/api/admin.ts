import apiClient from './client'
import type {
  DashboardStats,
  WorkerMonitorResponse,
  TaskListResponse,
  TaskDetailResponse,
  TaskStatisticsResponse,
  BatchRetryRequest,
  BatchRetryResponse,
  TaskRetryResponse,
  JobsDailyTrendResponse,
} from '@/features/admin/types'

export const adminApi = {
  getDashboardStats: () => apiClient.get<DashboardStats>('/admin/dashboard/stats'),
  getJobsDailyTrend: (params?: { days?: number }) =>
    apiClient.get<JobsDailyTrendResponse>('/admin/jobs/daily-trend', { params }),
  getWorkerStatus: () => apiClient.get<WorkerMonitorResponse>('/admin/workers'),
  getTasks: (params: {
    status?: string
    taskType?: string
    workerId?: string
    keyword?: string
    startTime?: string
    endTime?: string
    page?: number
    pageSize?: number
  }) => apiClient.get<TaskListResponse>('/admin/tasks', { params }),
  getTaskDetail: (taskId: string) => apiClient.get<TaskDetailResponse>(`/admin/tasks/${taskId}`),
  retryTask: (taskId: string) => apiClient.post<TaskRetryResponse>(`/admin/tasks/${taskId}/retry`),
  batchRetry: (payload: BatchRetryRequest) =>
    apiClient.post<BatchRetryResponse>('/admin/tasks/batch-retry', payload),
  getTaskStatistics: (params: {
    status?: string
    taskType?: string
    startTime?: string
    endTime?: string
  }) => apiClient.get<TaskStatisticsResponse>('/admin/tasks/statistics', { params }),
  getTaskTypes: () => apiClient.get<Array<{ value: string; displayName: string }>>('/tasks/types'),
}
