export interface MetricCount {
  total: number
  todayNew: number
}

export interface TaskMetric extends MetricCount {
  running: number
  failed: number
}

export interface FloatMetricCount {
  total: number
  todayNew: number
}

export interface DashboardStats {
  users: MetricCount
  jobs: MetricCount
  matches: MetricCount
  applications: MetricCount
  tasks: TaskMetric
  aiTokens: MetricCount
  aiCost: FloatMetricCount
}

export interface JobsDailyTrendPoint {
  date: string
  count: number
}

export interface JobsDailyTrendSeries {
  name: string
  points: JobsDailyTrendPoint[]
}

export interface JobsDailyTrendResponse {
  timezone: string
  startDate: string
  endDate: string
  sources: string[]
  series: JobsDailyTrendSeries[]
}

export interface JobsTimeScatterPoint {
  bucketStart: string
  source: string
  count: number
}

export interface JobsTimeScatterResponse {
  timezone: string
  bucketMinutes: number
  startDateTime: string
  endDateTime: string
  sources: string[]
  points: JobsTimeScatterPoint[]
}

export interface AIUsageDailyTrendPoint {
  date: string
  value: number
}

export interface AIUsageDailyTrendSeries {
  name: string
  points: AIUsageDailyTrendPoint[]
}

export interface AIUsageDailyTrendResponse {
  timezone: string
  startDate: string
  endDate: string
  models: string[]
  series: AIUsageDailyTrendSeries[]
}

export interface WorkerStatus {
  id: string
  hostname: string
  status: string
  currentTasks: number
  lastHeartbeat: string | null
}

export interface WorkerMonitorResponse {
  activeCount: number
  queuedTasks: number
  runningTasks: number
  workers: WorkerStatus[]
}

export interface TaskListItem {
  id: string
  taskName: string
  taskType?: string
  status: string
  workerId?: string
  celeryTaskId?: string
  retryCount: number
  maxRetries: number
  executionTimeMs?: number
  errorMessage?: string
  aiCost: number
  entityType: string
  entityId: string
  userId?: number
  workflowId: string
  createdAt: string
  startedAt?: string
  completedAt?: string
}

export interface TaskListStats {
  failed: number
  timeout: number
  success: number
  running: number
  taskTypeDistribution: Record<string, number>
}

export interface TaskListResponse {
  items: TaskListItem[]
  total: number
  page: number
  pageSize: number
  totalPages: number
  stats: TaskListStats
}

export interface AICallDetail {
  id: string
  model: string
  agentId?: string
  inputTokens?: number
  outputTokens?: number
  totalTokens?: number
  estimatedCost?: number
  latencyMs?: number
  status: string
  errorMessage?: string
  createdAt: string
}

export interface TaskDetailResponse {
  id: string
  taskName: string
  taskType?: string
  status: string
  workerId?: string
  celeryTaskId?: string
  retryCount: number
  maxRetries: number
  executionTimeMs?: number
  errorMessage?: string
  inputData?: Record<string, unknown>
  outputData?: Record<string, unknown>
  entityType: string
  entityId: string
  userId?: number
  workflowId: string
  createdAt: string
  startedAt?: string
  completedAt?: string
  aiCalls: AICallDetail[]
}

export interface TaskRetryResponse {
  message: string
  taskId: string
  status: string
  retriedTaskIds: string[]
}

export interface BatchRetryRequest {
  taskIds: string[]
}

export interface BatchRetryResult {
  originalTaskId: string
  newTaskId?: string
  status: string
  error?: string
}

export interface BatchRetryResponse {
  message: string
  successCount: number
  failedCount: number
  results: BatchRetryResult[]
}

export interface TaskTypeStats {
  taskType: string
  avgDurationMs?: number
  failureRatePct?: number
  todayFailureRatePct?: number
  trend: string
  dailyCost: number
  totalCount: number
}

export interface TaskStatisticsResponse {
  taskTypeStats: TaskTypeStats[]
}
