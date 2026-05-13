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
  AIUsageDailyTrendResponse,
  JobsDailyTrendResponse,
  JobsTimeScatterResponse,
  TasksDailyTrendResponse,
  TasksExecutionTimeResponse,
} from '@/features/admin/types'

export const adminApi = {
  getDashboardStats: () => apiClient.get<DashboardStats>('/admin/dashboard/stats'),
  getJobsDailyTrend: (params?: { days?: number }) =>
    apiClient.get<JobsDailyTrendResponse>('/admin/jobs/daily-trend', { params }),
  getJobsTimeScatter: (params?: { days?: number }) =>
    apiClient.get<JobsTimeScatterResponse>('/admin/jobs/time-scatter', { params }),
  getAITokensDailyTrend: (params?: { days?: number }) =>
    apiClient.get<AIUsageDailyTrendResponse>('/admin/ai/tokens-daily-trend', { params }),
  getAICostDailyTrend: (params?: { days?: number }) =>
    apiClient.get<AIUsageDailyTrendResponse>('/admin/ai/cost-daily-trend', { params }),
  getTasksDailyTrend: (params?: { days?: number }) =>
    apiClient.get<TasksDailyTrendResponse>('/admin/tasks/daily-trend', { params }),
  getTasksExecutionTime: (params?: { days?: number }) =>
    apiClient.get<TasksExecutionTimeResponse>('/admin/tasks/execution-time', { params }),
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
