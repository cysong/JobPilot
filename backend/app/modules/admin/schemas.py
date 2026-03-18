"""Pydantic schemas for admin APIs (dashboard, monitoring, tasks)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class AdminBase(BaseModel):
    """Base model enabling population by field name for alias support."""

    model_config = ConfigDict(populate_by_name=True)


# ===== Dashboard Stats =====
class MetricCount(AdminBase):
    total: int
    today_new: int = Field(..., alias="todayNew")


class TaskMetric(MetricCount):
    running: int
    failed: int


class FloatMetricCount(AdminBase):
    total: float
    today_new: float = Field(..., alias="todayNew")


class DashboardStats(AdminBase):
    users: MetricCount
    jobs: MetricCount
    matches: MetricCount
    applications: MetricCount
    tasks: TaskMetric
    ai_tokens: MetricCount = Field(..., alias="aiTokens")
    ai_cost: FloatMetricCount = Field(..., alias="aiCost")


class JobsDailyTrendPoint(AdminBase):
    date: str
    count: int


class JobsDailyTrendSeries(AdminBase):
    name: str
    points: List[JobsDailyTrendPoint]


class JobsDailyTrendResponse(AdminBase):
    timezone: str
    start_date: str = Field(..., alias="startDate")
    end_date: str = Field(..., alias="endDate")
    sources: List[str]
    series: List[JobsDailyTrendSeries]


class JobsTimeScatterPoint(AdminBase):
    bucket_start: datetime = Field(..., alias="bucketStart")
    source: str
    count: int


class JobsTimeScatterResponse(AdminBase):
    timezone: str
    bucket_minutes: int = Field(..., alias="bucketMinutes")
    start_date_time: datetime = Field(..., alias="startDateTime")
    end_date_time: datetime = Field(..., alias="endDateTime")
    sources: List[str]
    points: List[JobsTimeScatterPoint]


# ===== Worker Monitor =====
class WorkerStatus(AdminBase):
    id: str
    hostname: str
    status: str  # "active" | "offline"
    current_tasks: int = Field(..., alias="currentTasks")
    last_heartbeat: Optional[datetime] = Field(None, alias="lastHeartbeat")


class WorkerMonitorResponse(AdminBase):
    active_count: int = Field(..., alias="activeCount")
    queued_tasks: int = Field(..., alias="queuedTasks")
    running_tasks: int = Field(..., alias="runningTasks")
    workers: List[WorkerStatus]


# ===== Task List =====
class TaskListItem(AdminBase):
    id: str
    task_name: str = Field(..., alias="taskName")
    task_type: Optional[str] = Field(None, alias="taskType")
    status: str
    worker_id: Optional[str] = Field(None, alias="workerId")
    celery_task_id: Optional[str] = Field(None, alias="celeryTaskId")
    retry_count: int = Field(..., alias="retryCount")
    max_retries: int = Field(..., alias="maxRetries")
    execution_time_ms: Optional[int] = Field(None, alias="executionTimeMs")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    ai_cost: float = Field(..., alias="aiCost")
    entity_type: str = Field(..., alias="entityType")
    entity_id: str = Field(..., alias="entityId")
    user_id: Optional[int] = Field(None, alias="userId")
    workflow_id: str = Field(..., alias="workflowId")
    created_at: datetime = Field(..., alias="createdAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")


class TaskListStats(AdminBase):
    failed: int
    timeout: int
    success: int
    running: int
    task_type_distribution: Dict[str, int] = Field(..., alias="taskTypeDistribution")


class TaskListResponse(AdminBase):
    items: List[TaskListItem]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")
    total_pages: int = Field(..., alias="totalPages")
    stats: TaskListStats


# ===== Task Details =====
class AICallDetail(AdminBase):
    id: str
    model: str
    model_provider: str = Field(..., alias="modelProvider")
    agent_id: Optional[str] = Field(None, alias="agentId")
    input_tokens: Optional[int] = Field(None, alias="inputTokens")
    output_tokens: Optional[int] = Field(None, alias="outputTokens")
    total_tokens: Optional[int] = Field(None, alias="totalTokens")
    estimated_cost: Optional[float] = Field(None, alias="estimatedCost")
    latency_ms: Optional[int] = Field(None, alias="latencyMs")
    status: str
    error_message: Optional[str] = Field(None, alias="errorMessage")
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(..., alias="createdAt")


class TaskDetailResponse(AdminBase):
    id: str
    task_name: str = Field(..., alias="taskName")
    task_type: Optional[str] = Field(None, alias="taskType")
    status: str
    worker_id: Optional[str] = Field(None, alias="workerId")
    celery_task_id: Optional[str] = Field(None, alias="celeryTaskId")
    retry_count: int = Field(..., alias="retryCount")
    max_retries: int = Field(..., alias="maxRetries")
    execution_time_ms: Optional[int] = Field(None, alias="executionTimeMs")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    input_data: Optional[Dict[str, Any]] = Field(None, alias="inputData")
    output_data: Optional[Dict[str, Any]] = Field(None, alias="outputData")
    entity_type: str = Field(..., alias="entityType")
    entity_id: str = Field(..., alias="entityId")
    user_id: Optional[int] = Field(None, alias="userId")
    workflow_id: str = Field(..., alias="workflowId")
    created_at: datetime = Field(..., alias="createdAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    ai_calls: List[AICallDetail] = Field(default_factory=list, alias="aiCalls")


# ===== Task Retry =====
class TaskRetryResponse(AdminBase):
    message: str
    task_id: str = Field(..., alias="taskId")
    status: str
    retried_task_ids: List[str] = Field(default_factory=list, alias="retriedTaskIds")


class BatchRetryRequest(AdminBase):
    task_ids: List[str] = Field(..., alias="taskIds")


class BatchRetryResult(AdminBase):
    original_task_id: str = Field(..., alias="originalTaskId")
    new_task_id: Optional[str] = Field(None, alias="newTaskId")
    status: str  # "success" | "failed"
    error: Optional[str] = None


class BatchRetryResponse(AdminBase):
    message: str
    success_count: int = Field(..., alias="successCount")
    failed_count: int = Field(..., alias="failedCount")
    results: List[BatchRetryResult]


# ===== Task Statistics =====
class TaskTypeStats(AdminBase):
    task_type: str = Field(..., alias="taskType")
    avg_duration_ms: Optional[float] = Field(None, alias="avgDurationMs")
    failure_rate_pct: Optional[float] = Field(None, alias="failureRatePct")
    today_failure_rate_pct: Optional[float] = Field(None, alias="todayFailureRatePct")
    trend: str  # "up" | "down" | "stable"
    daily_cost: float = Field(..., alias="dailyCost")
    total_count: int = Field(..., alias="totalCount")


class TaskStatisticsResponse(AdminBase):
    task_type_stats: List[TaskTypeStats] = Field(..., alias="taskTypeStats")
