"""Pydantic schemas for admin APIs (dashboard, monitoring, tasks)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ===== Dashboard Stats =====
class MetricCount(BaseModel):
    total: int
    today_new: int = Field(..., alias="todayNew")


class TaskMetric(MetricCount):
    running: int
    failed: int


class DashboardStats(BaseModel):
    users: MetricCount
    jobs: MetricCount
    matches: MetricCount
    applications: MetricCount
    tasks: TaskMetric


# ===== Worker Monitor =====
class WorkerStatus(BaseModel):
    id: str
    hostname: str
    status: str  # "active" | "offline"
    current_tasks: int = Field(..., alias="currentTasks")
    last_heartbeat: Optional[datetime] = Field(None, alias="lastHeartbeat")


class WorkerMonitorResponse(BaseModel):
    active_count: int = Field(..., alias="activeCount")
    queued_tasks: int = Field(..., alias="queuedTasks")
    running_tasks: int = Field(..., alias="runningTasks")
    workers: List[WorkerStatus]


# ===== Task List =====
class TaskListItem(BaseModel):
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


class TaskListStats(BaseModel):
    failed: int
    timeout: int
    success: int
    running: int
    task_type_distribution: Dict[str, int] = Field(..., alias="taskTypeDistribution")


class TaskListResponse(BaseModel):
    items: List[TaskListItem]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")
    total_pages: int = Field(..., alias="totalPages")
    stats: TaskListStats


# ===== Task Details =====
class AICallDetail(BaseModel):
    id: str
    model: str
    agent_id: Optional[str] = Field(None, alias="agentId")
    input_tokens: Optional[int] = Field(None, alias="inputTokens")
    output_tokens: Optional[int] = Field(None, alias="outputTokens")
    total_tokens: Optional[int] = Field(None, alias="totalTokens")
    estimated_cost: Optional[float] = Field(None, alias="estimatedCost")
    latency_ms: Optional[int] = Field(None, alias="latencyMs")
    status: str
    error_message: Optional[str] = Field(None, alias="errorMessage")
    created_at: datetime = Field(..., alias="createdAt")


class TaskDetailResponse(BaseModel):
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
class TaskRetryResponse(BaseModel):
    message: str
    original_task_id: str = Field(..., alias="originalTaskId")
    new_task_id: str = Field(..., alias="newTaskId")
    status: str


class BatchRetryRequest(BaseModel):
    task_ids: List[str] = Field(..., alias="taskIds")


class BatchRetryResult(BaseModel):
    original_task_id: str = Field(..., alias="originalTaskId")
    new_task_id: Optional[str] = Field(None, alias="newTaskId")
    status: str  # "success" | "failed"
    error: Optional[str] = None


class BatchRetryResponse(BaseModel):
    message: str
    success_count: int = Field(..., alias="successCount")
    failed_count: int = Field(..., alias="failedCount")
    results: List[BatchRetryResult]


# ===== Task Statistics =====
class TaskTypeStats(BaseModel):
    task_type: str = Field(..., alias="taskType")
    avg_duration_ms: Optional[float] = Field(None, alias="avgDurationMs")
    failure_rate_pct: Optional[float] = Field(None, alias="failureRatePct")
    today_failure_rate_pct: Optional[float] = Field(None, alias="todayFailureRatePct")
    trend: str  # "up" | "down" | "stable"
    daily_cost: float = Field(..., alias="dailyCost")
    total_count: int = Field(..., alias="totalCount")


class TaskStatisticsResponse(BaseModel):
    task_type_stats: List[TaskTypeStats] = Field(..., alias="taskTypeStats")
