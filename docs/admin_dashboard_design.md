# 管理员监控Dashboard设计文档

**版本:** 1.1
**日期:** 2025-01-23
**状态:** 设计已批准

---

## 概述

本文档描述管理员Dashboard的设计方案,用于监控系统指标、Worker状态和任务执行情况。Dashboard为管理员提供系统健康状况和任务性能的实时洞察。

**核心功能:**
- 系统级指标统计(含今日新增)
- Worker和队列监控
- 高级任务筛选和搜索
- 任务重试功能(单个和批量)
- 任务执行统计分析

**实现方案:** 基础增强型 (第一阶段)
- 手动刷新(第一阶段不使用WebSocket)
- 可扩展架构,为后续实时更新预留接口
- 完整的任务监控和增强分析能力

**架构方案:**
- **独立入口:** Admin使用独立登录页面 `/admin/login`
- **复用布局:** Admin页面复用MainLayout,根据角色显示admin菜单
- **统一权限验证:** Router级别统一验证ADMIN角色,避免重复代码

---

## 系统架构

### 模块结构

```
backend/app/modules/admin/
├── __init__.py
├── router.py              # API路由端点 (Router级别统一权限验证)
├── service.py             # 业务逻辑层
├── schemas.py             # 请求/响应模型
└── dependencies.py        # 管理员角色验证 (require_admin)

frontend/src/
├── features/
│   ├── auth/
│   │   └── Login.tsx             # 登录组件(支持isAdmin prop)
│   └── admin/
│       ├── components/
│       │   ├── DashboardStats.tsx        # 统计卡片
│       │   ├── WorkerMonitor.tsx         # Worker状态表格
│       │   ├── TaskList.tsx              # 任务列表(带筛选)
│       │   ├── TaskDetailPanel.tsx       # 可展开的任务详情
│       │   ├── TaskStatistics.tsx        # 任务类型统计表
│       │   └── TaskFilters.tsx           # 高级筛选控件
│       ├── hooks/
│       │   ├── useDashboardStats.ts      # Dashboard统计数据
│       │   ├── useWorkerStatus.ts        # Worker状态
│       │   └── useTasks.ts               # 任务列表
│       ├── AdminDashboardPage.tsx        # 主Dashboard页面
│       └── TaskMonitorPage.tsx           # 任务监控页面
└── components/
    ├── layout/
    │   └── MainLayout.tsx        # 复用的主布局(根据角色显示admin菜单)
    └── ProtectedRoute.tsx        # 权限守卫(支持requiredRole)
```

---

## UI设计

### 页面1: Dashboard主页

```
┌─────────────────────────────────────────────────────────────┐
│              管理员监控Dashboard                              │
│                                    [刷新] 最后更新: 2分钟前   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📊 系统指标                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 用户数   │ │ Job数    │ │ 匹配数   │ │ 申请数   │       │
│  │  1,234   │ │  5,678   │ │ 12,345   │ │   890    │       │
│  │ 今日+8   │ │ 今日+15  │ │ 今日+45  │ │ 今日+8   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                               │
│  ┌──────────┐                                                │
│  │ 任务数   │  ← 点击打开任务监控页面                        │
│  │   456    │                                                │
│  │ 今日+12  │                                                │
│  └──────────┘                                                │
│                                                               │
│ ───────────────────────────────────────────────────────────│
│                                                               │
│  ⚙️  Worker & 队列监控                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 活跃Worker: 3    队列积压: 12任务    正在运行: 8    │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Worker ID │ 主机名      │ 状态   │ 任务数 │ 最后心跳 │   │
│  │ worker-1  │ server-01   │ ✓活跃  │   3    │  2秒前   │   │
│  │ worker-2  │ server-02   │ ✓活跃  │   5    │  1秒前   │   │
│  │ worker-3  │ server-03   │ ✓活跃  │   0    │  3秒前   │   │
│  │ worker-4  │ server-04   │ ✗离线  │   -    │ 10分前   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  💡 说明: 红色=离线, 绿色=活跃                                │
│  📝 预留: 后续可添加WebSocket实时更新                         │
└─────────────────────────────────────────────────────────────┘
```

### 页面2: 任务监控页面

```
┌─────────────────────────────────────────────────────────────┐
│              任务监控                        [返回Dashboard]  │
│                                    [刷新] 最后更新: 1分钟前   │
├─────────────────────────────────────────────────────────────┤
│  🔍 高级筛选                                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 状态: [✓失败] [✓超时(>10分钟)] [ 成功] [ 运行中]      │  │
│  │ 任务类型: [全部▼]  Worker: [全部▼]  时间: [最近24h▼] │  │
│  │ 关键词: [____________]  [搜索]  [清空筛选]            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  📊 筛选结果统计                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 失败: 15  超时: 8  成功: 234  总计: 257               │  │
│  │ 任务类型分布: Job分析(45%) 简历定制(30%) 其他(25%)    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  📋 任务列表  [批量重试选中任务 (0)]                         │
│  ┌─┬────────────┬────────┬────────┬────────┬────────┬─────┐│
│  │☐│任务名       │状态    │Worker  │重试    │耗时    │成本 ││
│  ├─┼────────────┼────────┼────────┼────────┼────────┼─────┤│
│  │☐│analyze_job │⚠️失败  │worker-1│3/3     │2m 30s  │$0.05││
│  │ │#task-1234  │        │        │        │        │🔄📊📋││
│  ├─┼────────────┼────────┼────────┼────────┼────────┼─────┤│
│  │☐│tailor_resu │⏱️运行中│worker-2│1/3     │12m 5s⚠│$0.15││
│  │ │#task-1235  │        │        │        │超时!   │🔄📊📋││
│  ├─┼────────────┼────────┼────────┼────────┼────────┼─────┤│
│  │☐│cover_lette │⚠️失败  │worker-1│2/3     │1m 45s  │$0.03││
│  │ │#task-1236  │        │        │        │        │🔄📊📋││
│  └─┴────────────┴────────┴────────┴────────┴────────┴─────┘│
│                                                               │
│  分页: [上一页] 1 2 3 4 5 [下一页]  每页20条, 共257条         │
│                                                               │
│  点击某行展开详情 ▼                                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 📋 任务详情: task-1234                                 │  │
│  │ ├─ 基本信息                                            │  │
│  │ │  任务类型: JOB_ANALYSIS                             │  │
│  │ │  关联实体: Job #12345                               │  │
│  │ │  用户ID: user-789                                   │  │
│  │ │  工作流ID: wf-456                                   │  │
│  │ │  创建时间: 2025-01-23 14:30:00                      │  │
│  │ │  开始时间: 2025-01-23 14:30:05                      │  │
│  │ │  完成时间: 2025-01-23 14:32:35                      │  │
│  │ │  Celery任务ID: abc-123-def                          │  │
│  │ ├─ 错误信息                                            │  │
│  │ │  OpenAI API rate limit exceeded. 请60秒后重试。     │  │
│  │ │  (错误代码: 429)                                    │  │
│  │ ├─ 重试历史                                            │  │
│  │ │  第1次: 14:30:05 → 失败 (1分20秒)                  │  │
│  │ │  第2次: 14:31:25 → 失败 (55秒)                     │  │
│  │ │  第3次: 14:32:20 → 失败 (15秒)                     │  │
│  │ ├─ 输入参数                                            │  │
│  │ │  { job_id: 12345, user_id: 789, workflow_id: 456 } │  │
│  │ ├─ AI调用指标 (如有)                                  │  │
│  │ │  模型: gpt-4  输入tokens: 1,234  输出: 567         │  │
│  │ │  预估成本: $0.05                                    │  │
│  │ └─ 操作                                                │  │
│  │    [🔄 立即重试]  [📋 复制ID]  [📊 查看相关任务]      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│ ───────────────────────────────────────────────────────────│
│                                                               │
│  📊 任务执行统计 (当前筛选范围)                               │
│  ┌─────────────────┬──────────┬──────────┬──────────────┐  │
│  │ 任务类型        │ 平均耗时 │ 失败率   │ 每日成本     │  │
│  ├─────────────────┼──────────┼──────────┼──────────────┤  │
│  │ Job分析         │ 1分30秒  │ 5% ⬇️   │ $45.67/天    │  │
│  │ 简历定制        │ 3分45秒  │ 12% ⬆️  │ $89.23/天    │  │
│  │ Cover Letter    │ 2分10秒  │ 8% →    │ $34.56/天    │  │
│  │ 匹配计算        │ 45秒     │ 2% ⬇️   │ $12.34/天    │  │
│  └─────────────────┴──────────┴──────────┴──────────────┘  │
│                                                               │
│  💡 图例: ⬆️ 上升  ⬇️ 下降  → 持平                           │
└─────────────────────────────────────────────────────────────┘

图标说明: 🔄 重试  📊 统计  📋 详情  ⚠️ 失败  ✓ 成功  ⏱️ 运行中
```

---

## 数据库查询

### 查询1: Dashboard统计数据

```sql
-- 用户数 + 今日新增
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as today_new
FROM users;

-- Job数 + 今日新增
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as today_new
FROM seek_jobs
WHERE is_deleted = FALSE;

-- 匹配数 + 今日新增
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN updated_at >= CURRENT_DATE THEN 1 END) as today_new
FROM job_matches;

-- 申请数 + 今日新增
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as today_new
FROM applications
WHERE is_deleted = FALSE;

-- 任务数 + 今日新增 + 正在运行
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as today_new,
  COUNT(CASE WHEN status = 'RUNNING' THEN 1 END) as running_count
FROM task_executions;
```

### 查询2: Worker状态

使用Celery Inspect API:

```python
from celery import current_app

inspect = current_app.control.inspect()

# Get active workers
active_workers = inspect.active()  # Returns: {worker_name: [task_list]}

# Get worker stats
stats = inspect.stats()  # Returns: {worker_name: stats_dict}

# Calculate task count per worker
task_counts = {
    worker: len(tasks)
    for worker, tasks in (active_workers or {}).items()
}
```

### 查询3: 任务列表 (带筛选和分页)

```sql
SELECT
  te.id,
  te.task_name,
  te.task_type,
  te.status,
  te.worker_id,
  te.retry_count,
  te.max_retries,
  te.execution_time_ms,
  te.error_message,
  te.created_at,
  te.started_at,
  te.completed_at,
  te.entity_type,
  te.entity_id,
  te.user_id,
  te.workflow_id,
  te.celery_task_id,
  -- AI cost (aggregated from ai_calls)
  COALESCE(SUM(ac.estimated_cost), 0) as ai_cost
FROM task_executions te
LEFT JOIN ai_calls ac ON ac.task_id = te.id
WHERE
  -- Status filter (array of statuses)
  (:status_filter IS NULL OR te.status = ANY(:status_filter))
  -- Timeout filter (>10 minutes = 600 seconds)
  AND (:include_timeout = FALSE OR
       (te.status = 'RUNNING' AND
        EXTRACT(EPOCH FROM (NOW() - te.started_at)) > 600))
  -- Task type filter
  AND (:task_type IS NULL OR te.task_type = :task_type)
  -- Worker filter
  AND (:worker_id IS NULL OR te.worker_id = :worker_id)
  -- Time range filter
  AND te.created_at >= :start_time
  AND te.created_at <= :end_time
  -- Keyword search
  AND (:keyword IS NULL OR
       te.task_name ILIKE '%' || :keyword || '%' OR
       te.id ILIKE '%' || :keyword || '%' OR
       te.entity_id ILIKE '%' || :keyword || '%')
GROUP BY te.id
ORDER BY te.created_at DESC
LIMIT :page_size OFFSET :offset;

-- Count query for pagination
SELECT COUNT(DISTINCT te.id)
FROM task_executions te
WHERE [same filters as above];
```

### 查询4: 任务执行统计

```sql
SELECT
  task_type,
  -- Average duration
  AVG(execution_time_ms) as avg_duration_ms,
  -- Overall failure rate
  ROUND(
    COUNT(CASE WHEN status = 'FAILED' THEN 1 END)::NUMERIC /
    NULLIF(COUNT(*)::NUMERIC, 0) * 100,
    2
  ) as failure_rate_pct,
  -- Today's failure rate (for trend comparison)
  ROUND(
    COUNT(CASE WHEN status = 'FAILED' AND created_at >= CURRENT_DATE THEN 1 END)::NUMERIC /
    NULLIF(COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END)::NUMERIC, 0) * 100,
    2
  ) as today_failure_rate_pct,
  -- Daily cost (today only)
  COALESCE(SUM(
    CASE WHEN ac.created_at >= CURRENT_DATE
    THEN ac.estimated_cost
    ELSE 0 END
  ), 0) as daily_cost,
  -- Total count
  COUNT(*) as total_count
FROM task_executions te
LEFT JOIN ai_calls ac ON ac.task_id = te.id
WHERE te.created_at >= NOW() - INTERVAL '30 days'
  AND (:status_filter IS NULL OR te.status = ANY(:status_filter))
  -- Apply same filters as task list query
GROUP BY te.task_type
ORDER BY COUNT(*) DESC;
```

### 查询5: 任务详情(含AI调用记录)

```sql
-- Main task info
SELECT
  te.*,
  COALESCE(SUM(ac.estimated_cost), 0) as total_ai_cost
FROM task_executions te
LEFT JOIN ai_calls ac ON ac.task_id = te.id
WHERE te.id = :task_id
GROUP BY te.id;

-- AI calls for this task
SELECT
  id,
  model,
  agent_id,
  input_tokens,
  output_tokens,
  total_tokens,
  estimated_cost,
  latency_ms,
  status,
  error_message,
  created_at
FROM ai_calls
WHERE task_id = :task_id
ORDER BY created_at ASC;

-- Note: Retry history is reconstructed from task execution records
-- Since we don't store individual retry attempts, we need to:
-- 1. Show current retry_count
-- 2. Calculate approximate attempt times based on retry_backoff
```

---

## API设计

### 基础路径

```
/api/v1/admin/*
```

所有端点均需要`ADMIN`角色认证。

---

### API 1: Dashboard统计数据

**端点:**
```
GET /api/v1/admin/dashboard/stats
```

**响应:**
```json
{
  "users": {
    "total": 1234,
    "todayNew": 8
  },
  "jobs": {
    "total": 5678,
    "todayNew": 15
  },
  "matches": {
    "total": 12345,
    "todayNew": 45
  },
  "applications": {
    "total": 890,
    "todayNew": 8
  },
  "tasks": {
    "total": 456,
    "todayNew": 12,
    "running": 8,
    "failed": 15
  }
}
```

---

### API 2: Worker状态

**端点:**
```
GET /api/v1/admin/workers
```

**响应:**
```json
{
  "activeCount": 3,
  "queuedTasks": 12,
  "runningTasks": 8,
  "workers": [
    {
      "id": "worker-1",
      "hostname": "server-01",
      "status": "active",
      "currentTasks": 3,
      "lastHeartbeat": "2025-01-23T14:30:00Z"
    },
    {
      "id": "worker-4",
      "hostname": "server-04",
      "status": "offline",
      "currentTasks": 0,
      "lastHeartbeat": "2025-01-23T14:20:00Z"
    }
  ]
}
```

**状态判定逻辑:**
- `active`: 最后心跳时间 < 5分钟前
- `offline`: 最后心跳时间 >= 5分钟前

---

### API 3: 任务列表 (带筛选和分页)

**端点:**
```
GET /api/v1/admin/tasks
  ?status=FAILED,RUNNING              # 逗号分隔的状态值
  &includeTimeout=true                # 包含运行超过10分钟的任务
  &taskType=JOB_ANALYSIS              # 可选: 任务类型筛选
  &workerId=worker-1                  # 可选: Worker筛选
  &startTime=2025-01-22T00:00:00Z     # 时间范围起始
  &endTime=2025-01-23T23:59:59Z       # 时间范围结束
  &keyword=12345                      # 在name/id/entity_id中搜索
  &page=1                             # 页码 (从1开始)
  &pageSize=20                        # 每页条数
```

**响应:**
```json
{
  "items": [
    {
      "id": "task-1234",
      "taskName": "analyze_job_async",
      "taskType": "JOB_ANALYSIS",
      "status": "FAILED",
      "workerId": "worker-1",
      "celeryTaskId": "abc-123-def",
      "retryCount": 3,
      "maxRetries": 3,
      "executionTimeMs": 150000,
      "errorMessage": "OpenAI API rate limit exceeded...",
      "aiCost": 0.05,
      "entityType": "job",
      "entityId": "12345",
      "userId": 789,
      "workflowId": "wf-456",
      "createdAt": "2025-01-23T14:30:00Z",
      "startedAt": "2025-01-23T14:30:05Z",
      "completedAt": "2025-01-23T14:32:35Z"
    }
  ],
  "total": 257,
  "page": 1,
  "pageSize": 20,
  "totalPages": 13,
  "stats": {
    "failed": 15,
    "timeout": 8,
    "success": 234,
    "running": 0,
    "taskTypeDistribution": {
      "JOB_ANALYSIS": 45,
      "TAILOR_RESUME": 30,
      "COVER_LETTER": 25
    }
  }
}
```

---

### API 4: 任务详情

**端点:**
```
GET /api/v1/admin/tasks/:taskId
```

**响应:**
```json
{
  "id": "task-1234",
  "taskName": "analyze_job_async",
  "taskType": "JOB_ANALYSIS",
  "status": "FAILED",
  "workerId": "worker-1",
  "celeryTaskId": "abc-123-def",
  "retryCount": 3,
  "maxRetries": 3,
  "executionTimeMs": 150000,
  "errorMessage": "OpenAI API rate limit exceeded. Please retry after 60 seconds. (Error code: 429)",
  "inputData": {
    "job_id": 12345,
    "user_id": 789,
    "workflow_id": "wf-456"
  },
  "outputData": null,
  "entityType": "job",
  "entityId": "12345",
  "userId": 789,
  "workflowId": "wf-456",
  "createdAt": "2025-01-23T14:30:00Z",
  "startedAt": "2025-01-23T14:30:05Z",
  "completedAt": "2025-01-23T14:32:35Z",
  "aiCalls": [
    {
      "id": "ai-call-123",
      "model": "gpt-4",
      "agentId": "job_analyzer",
      "inputTokens": 1234,
      "outputTokens": 567,
      "totalTokens": 1801,
      "estimatedCost": 0.05,
      "latencyMs": 2500,
      "status": "COMPLETED",
      "createdAt": "2025-01-23T14:30:10Z"
    }
  ]
}
```

**注意:** 重试历史从`retryCount`和时间戳推断。系统不存储每次重试的详细日志。

---

### API 5: 重试任务

**端点:**
```
POST /api/v1/admin/tasks/:taskId/retry
```

**请求体:** (空)

**响应:**
```json
{
  "message": "任务重试已提交",
  "originalTaskId": "task-1234",
  "newTaskId": "task-5678",
  "status": "PENDING"
}
```

**错误响应:**
```json
{
  "code": 400,
  "message": "无法重试状态为SUCCESS的任务",
  "data": null
}
```

---

### API 6: 批量重试任务

**端点:**
```
POST /api/v1/admin/tasks/batch-retry
```

**请求体:**
```json
{
  "taskIds": ["task-1234", "task-1235", "task-1236"]
}
```

**响应:**
```json
{
  "message": "批量重试已提交",
  "successCount": 3,
  "failedCount": 0,
  "results": [
    {
      "originalTaskId": "task-1234",
      "newTaskId": "task-5678",
      "status": "success"
    },
    {
      "originalTaskId": "task-1235",
      "newTaskId": "task-5679",
      "status": "success"
    },
    {
      "originalTaskId": "task-1236",
      "newTaskId": "task-5680",
      "status": "success"
    }
  ]
}
```

**部分失败响应:**
```json
{
  "message": "批量重试完成(含错误)",
  "successCount": 2,
  "failedCount": 1,
  "results": [
    {
      "originalTaskId": "task-1234",
      "newTaskId": "task-5678",
      "status": "success"
    },
    {
      "originalTaskId": "task-1235",
      "error": "任务不存在",
      "status": "failed"
    },
    {
      "originalTaskId": "task-1236",
      "newTaskId": "task-5680",
      "status": "success"
    }
  ]
}
```

---

### API 7: 任务统计

**端点:**
```
GET /api/v1/admin/tasks/statistics
  ?status=FAILED,SUCCESS              # 可选: 状态筛选
  &taskType=JOB_ANALYSIS              # 可选: 任务类型筛选
  &startTime=2025-01-22T00:00:00Z     # 可选: 时间范围
  &endTime=2025-01-23T23:59:59Z
```

**响应:**
```json
{
  "taskTypeStats": [
    {
      "taskType": "JOB_ANALYSIS",
      "avgDurationMs": 90000,
      "failureRatePct": 5.0,
      "todayFailureRatePct": 3.5,
      "trend": "down",
      "dailyCost": 45.67,
      "totalCount": 150
    },
    {
      "taskType": "TAILOR_RESUME",
      "avgDurationMs": 225000,
      "failureRatePct": 12.0,
      "todayFailureRatePct": 15.2,
      "trend": "up",
      "dailyCost": 89.23,
      "totalCount": 95
    },
    {
      "taskType": "COVER_LETTER",
      "avgDurationMs": 130000,
      "failureRatePct": 8.0,
      "todayFailureRatePct": 8.1,
      "trend": "stable",
      "dailyCost": 34.56,
      "totalCount": 78
    }
  ]
}
```

**趋势计算规则:**
- `up`: `todayFailureRatePct > failureRatePct + 2%`
- `down`: `todayFailureRatePct < failureRatePct - 2%`
- `stable`: 其他情况

---

## 业务逻辑

### 任务重试逻辑

**何时允许重试:**
- 任务状态为`FAILED`或`RUNNING`(如检测到超时)
- 任务未在重试中(检查Celery队列)

**重试实现步骤:**
1. 创建新的`TaskExecution`记录:
   - 使用原任务相同的`input_data`
   - 使用相同的`workflow_id`, `entity_type`, `entity_id`, `user_id`
   - 状态设为`PENDING`
   - `retry_count`重置为0
2. 使用原任务签名提交到Celery队列
3. 返回新任务ID给客户端

**注意:** 这会创建一个新的任务执行记录,而非增加原任务的重试计数。原任务保持`FAILED`状态用于审计。

### Worker状态检测

**活跃 vs 离线:**
- Worker通过Celery每约30秒发送一次心跳
- Admin API检查最后心跳时间戳
- 如果`NOW() - last_heartbeat > 5分钟` → 标记为`offline`

**任务计数:**
- 查询Celery inspect API: `inspect.active()`
- 返回字典: `{worker_name: [list_of_active_tasks]}`
- 统计每个worker的任务数

### 超时检测

**逻辑:**
- 任务被认为"超时"如果:
  - 状态 = `RUNNING`
  - 且 `NOW() - started_at > 10分钟 (600秒)`

**注意:** 超时任务仍在运行(未被终止)。管理员可手动重试以强制新的尝试。

---

## 权限控制

### 管理员角色验证

所有admin端点需要用户角色 = `ADMIN`。

**实现 - Router级别统一验证:**

```python
# backend/app/modules/admin/dependencies.py
from fastapi import Depends, HTTPException, status
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.shared.enums import Role

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Verify current user has ADMIN role."""
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
```

**在router中使用 - Router级别依赖 (推荐):**

```python
# backend/app/modules/admin/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.admin.dependencies import require_admin
from app.modules.auth.models import User

# 在Router级别统一添加依赖,所有endpoint自动继承
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)]  # Router级别统一验证
)

# Endpoint无需单独添加require_admin
@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # 可选: 如果需要获取当前用户
):
    """Get dashboard statistics. (Auto-protected by router dependencies)"""
    ...

@router.get("/workers")
async def get_workers(db: AsyncSession = Depends(get_db)):
    """Get worker status. (Auto-protected by router dependencies)"""
    ...
```

**优点:**
- ✅ 避免每个endpoint重复添加`require_admin`
- ✅ 代码更简洁,易于维护
- ✅ 减少遗漏权限验证的风险

---

## 数据模型

### Pydantic Schemas

```python
# backend/app/modules/admin/schemas.py

from datetime import datetime
from typing import Optional, List, Dict, Any
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
```

---

## 实现任务清单

### 后端任务

**模块初始化:**
- [ ] 创建`backend/app/modules/admin/`模块
- [ ] 创建`__init__.py`, `router.py`, `service.py`, `schemas.py`, `dependencies.py`

**Service层 (`service.py`):**
- [ ] 实现`get_dashboard_stats()` - 查询所有5个指标
- [ ] 实现`get_worker_status()` - 使用Celery inspect API
- [ ] 实现`get_tasks()` - 带筛选和分页的任务列表
- [ ] 实现`get_task_detail()` - 单个任务详情(含AI调用)
- [ ] 实现`retry_task()` - 创建新任务执行
- [ ] 实现`batch_retry_tasks()` - 批量重试逻辑
- [ ] 实现`get_task_statistics()` - 按任务类型聚合统计

**Router层 (`router.py`):**
- [ ] 创建Admin Router,在Router级别添加`require_admin`依赖
- [ ] 定义7个API端点
- [ ] 添加适当的错误处理和响应模型
- [ ] 在`app/api/v1/__init__.py`中注册admin router

**测试:**
- [ ] Service层单元测试
- [ ] API端点集成测试
- [ ] 管理员角色授权测试

### 前端任务

**基础设施 (1天):**
- [ ] 修改`Login.tsx`支持`isAdmin` prop
- [ ] 增强`ProtectedRoute`支持`requiredRole` prop
- [ ] 添加admin路由到`App.tsx`
- [ ] 修改`MainLayout`侧边栏,根据角色显示admin菜单项

**Admin模块 (2-3天):**
- [ ] 创建`frontend/src/features/admin/`模块

**组件:**
- [ ] `DashboardStats.tsx` - 5个指标卡片(任务卡片可点击)
- [ ] `WorkerMonitor.tsx` - Worker状态表格
- [ ] `TaskFilters.tsx` - 高级筛选控件
- [ ] `TaskList.tsx` - 带复选框的任务表格
- [ ] `TaskDetailPanel.tsx` - 可展开的任务详情面板
- [ ] `TaskStatistics.tsx` - 任务类型统计表格

**页面:**
- [ ] `AdminDashboardPage.tsx` - 主Dashboard页面(统计+Worker)
- [ ] `TaskMonitorPage.tsx` - 任务监控页面(列表+筛选+统计)

**API集成 (`hooks/`):**
- [ ] `useDashboardStats.ts` - 获取Dashboard统计数据
- [ ] `useWorkerStatus.ts` - 获取Worker状态
- [ ] `useTasks.ts` - 获取任务列表(带筛选)
- [ ] `useTaskDetail.ts` - 获取单个任务详情
- [ ] `useRetryTask.ts` - 重试单个任务的mutation
- [ ] `useBatchRetry.ts` - 批量重试的mutation
- [ ] `useTaskStatistics.ts` - 获取任务统计

**测试:**
- [ ] 组件单元测试
- [ ] API调用集成测试
- [ ] 权限守卫测试

---

## 未来增强功能 (第二阶段)

### WebSocket实时更新

准备添加实时功能时:

**后端:**
- 添加WebSocket事件:
  - `dashboard:stats_update` - 广播统计数据变化
  - `workers:status_change` - Worker上线/离线事件
  - `tasks:status_change` - 任务状态更新
  - `tasks:new_task` - 新任务创建

**前端:**
- 用WebSocket订阅替换手动刷新
- 添加实时任务进度条
- 显示任务失败的实时通知

### 高级功能

- **任务历史趋势:** 显示任务量随时间变化的折线图
- **成本分析:** 按用户/项目详细分解AI成本
- **告警规则:** 可配置的失败率阈值告警
- **性能指标:** P50/P95/P99延迟百分位数
- **自定义Dashboard:** 用户自定义指标小部件

---

## 术语表

- **Worker:** 执行任务的Celery worker进程
- **队列:** Celery管理的基于Redis的任务队列
- **任务执行:** 运行任务的单次尝试(存储在`task_executions`表)
- **重试:** 为失败任务创建新的任务执行记录
- **超时:** 已运行超过10分钟的任务
- **AI成本:** 基于`ai_calls`表的AI token使用量预估成本
- **心跳:** Worker定期向Celery发送的状态更新

---

## 参考资料

- [Celery监控和管理指南](https://docs.celeryq.dev/en/stable/userguide/monitoring.html)
- [FastAPI依赖注入](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [React Query文档](https://tanstack.com/query/latest/docs/react/overview)

---

**文档版本历史:**

| 版本 | 日期       | 作者 | 变更说明                                      |
|------|-----------|------|-----------------------------------------------|
| 1.0  | 2025-01-23 | 系统 | 初始设计文档创建                              |
| 1.1  | 2025-01-23 | 系统 | 更新方案:复用MainLayout,Router级别统一权限验证 |
