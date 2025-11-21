# JobPilot 工作流系统设计方案

## 1. 设计方案概述

### 1.1 核心架构

JobPilot 采用 **Celery Canvas + 自定义状态机** 的混合架构：

- **Celery Canvas**: 负责任务编排和执行（chain, group, chord）
- **PostgreSQL 状态表**: 负责持久化状态跟踪和恢复
- **Redis**: 作为 Celery broker 和结果后端

**架构分层**：

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                     │
│  • 接收用户请求                                               │
│  • 创建工作流记录                                             │
│  • 返回 workflow_id                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestration Layer (Workflow Service)          │
│  • 构建 Celery Canvas DAG                                    │
│  • 管理任务依赖关系                                           │
│  • 处理工作流生命周期                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               Execution Layer (Celery Workers)               │
│  • 执行具体任务                                               │
│  • 调用 AI Agent                                             │
│  • 更新任务状态                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 数据库设计

**workflow_executions 表**（工作流执行记录）：

```sql
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY,
    workflow_type VARCHAR(50) NOT NULL,    -- 'job_analysis', 'application_generation'
    config_version VARCHAR(20) NOT NULL DEFAULT 'v1.0.0', -- 工作流配置版本
    user_id UUID NOT NULL,
    entity_id UUID,                        -- job_id 或 application_id
    status VARCHAR(20),                    -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    celery_task_id VARCHAR(255),          -- Celery 任务 ID
    input_data JSONB,                     -- 输入参数
    output_data JSONB,                    -- 输出结果
    error_message TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_workflow_user_status ON workflow_executions(user_id, status);
CREATE INDEX idx_workflow_type_status ON workflow_executions(workflow_type, status);
CREATE INDEX idx_workflow_version ON workflow_executions(workflow_type, config_version, created_at);
```

**task_executions 表**（任务执行记录）：

```sql
CREATE TABLE task_executions (
    id UUID PRIMARY KEY,
    workflow_id UUID REFERENCES workflow_executions(id),
    task_name VARCHAR(100) NOT NULL,       -- 'fetch_html', 'translate_job', etc.
    task_type VARCHAR(50),                 -- 'ai_agent', 'data_processing', 'api_call'
    status VARCHAR(20),                    -- 'pending', 'running', 'success', 'failed', 'retry'
    celery_task_id VARCHAR(255),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    execution_time_ms INT,                 -- 执行耗时（毫秒）
    worker_id VARCHAR(100),                -- 执行该任务的 worker
    depends_on JSONB,                      -- 依赖的任务 ID 列表 ['task_id_1', 'task_id_2']
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_task_workflow_status ON task_executions(workflow_id, status);
CREATE INDEX idx_task_name ON task_executions(task_name);
```

## 2. 数据流详解

### 2.1 Job 分析工作流数据流

**场景**: 用户点击"分析职位"按钮

```
用户点击 → API 请求 → 创建工作流 → Celery 执行 → 更新状态 → 前端轮询/WebSocket 通知

详细流程：

时间线 T0: 用户点击
─────────────────────────────────────────────────────────
  浏览器
    │
    │ POST /api/jobs/analyze
    │ { job_url: "https://example.com/job/123" }
    ▼
  FastAPI Server
    │
    ├─ 验证用户配额（剩余 AI 分析次数）
    │
    ├─ 创建 workflow_executions 记录
    │  {
    │    id: "wf-001",
    │    workflow_type: "job_analysis",
    │    user_id: "user-123",
    │    entity_id: "job-456",
    │    status: "pending",
    │    input_data: { job_url: "..." }
    │  }
    │
    ├─ 创建 4 个 task_executions 记录（预占位）
    │  - task-001: fetch_html (pending)
    │  - task-002: html_to_markdown (pending, depends_on: [task-001])
    │  - task-003: translate_job (pending, depends_on: [task-002])
    │  - task-004: extract_skills (pending, depends_on: [task-003])
    │
    ├─ 构建 Celery Chain
    │  chain(
    │    fetch_html.s("wf-001", "task-001", job_url),
    │    html_to_markdown.s("wf-001", "task-002"),
    │    translate_job.s("wf-001", "task-003"),
    │    extract_skills.s("wf-001", "task-004")
    │  ).apply_async()
    │
    ├─ 更新 workflow status = "running"
    │
    └─ 返回响应
       { workflow_id: "wf-001", status: "running" }


时间线 T0+2s: Celery Worker 1 执行第一个任务
─────────────────────────────────────────────────────────
  Celery Worker 1 (worker-node-1)
    │
    ├─ 接收任务: fetch_html("wf-001", "task-001", job_url)
    │
    ├─ 更新 task-001 状态
    │  UPDATE task_executions SET
    │    status='running',
    │    started_at=NOW(),
    │    worker_id='worker-node-1'
    │  WHERE id='task-001'
    │
    ├─ 执行爬取逻辑
    │  result = httpx.get(job_url)
    │  html_content = result.text
    │
    ├─ 更新 task-001 状态
    │  UPDATE task_executions SET
    │    status='success',
    │    output_data='{"html": "..."}',
    │    execution_time_ms=1850,
    │    completed_at=NOW()
    │  WHERE id='task-001'
    │
    └─ 返回结果给下一个任务
       return html_content


时间线 T0+5s: Celery Worker 2 执行第二个任务
─────────────────────────────────────────────────────────
  Celery Worker 2 (worker-node-2)
    │
    ├─ 接收任务: html_to_markdown("wf-001", "task-002", html_content)
    │
    ├─ 更新 task-002 状态 → running
    │
    ├─ 调用 markdownify 库转换
    │  markdown = markdownify.markdownify(html_content)
    │
    ├─ 更新 task-002 状态 → success
    │
    └─ 返回 markdown


时间线 T0+8s: AI Agent 任务（翻译）
─────────────────────────────────────────────────────────
  Celery Worker 3 (worker-node-1)
    │
    ├─ 接收任务: translate_job("wf-001", "task-003", markdown)
    │
    ├─ 更新 task-003 状态 → running
    │
    ├─ 调用 DeepSeek API
    │  client = OpenAI(
    │    api_key=DEEPSEEK_KEY,
    │    base_url="https://api.deepseek.com"
    │  )
    │
    │  response = client.chat.completions.create(
    │    model="deepseek-chat",
    │    messages=[{
    │      "role": "system",
    │      "content": "将职位描述翻译成中文"
    │    }, {
    │      "role": "user",
    │      "content": markdown
    │    }]
    │  )
    │
    │  translated = response.choices[0].message.content
    │
    ├─ 更新 task-003 状态 → success
    │  output_data = {"translated_text": translated}
    │
    └─ 返回 translated


时间线 T0+15s: AI Agent 任务（技能提取）
─────────────────────────────────────────────────────────
  Celery Worker 1 (worker-node-2)
    │
    ├─ 接收任务: extract_skills("wf-001", "task-004", translated)
    │
    ├─ 更新 task-004 状态 → running
    │
    ├─ 调用 OpenAI Agents SDK
    │  agent = Agent(
    │    name="SkillExtractor",
    │    model="gpt-4o",
    │    instructions="""
    │      从职位描述中提取：
    │      1. 必需技能（required_skills）
    │      2. 优选技能（preferred_skills）
    │      3. 学历要求（education）
    │      4. 年限要求（experience_years）
    │      返回 JSON 格式
    │    """
    │  )
    │
    │  result = agent.run(translated)
    │  skills_data = json.loads(result.output)
    │
    ├─ 更新数据库（保存提取结果）
    │  UPDATE jobs SET
    │    required_skills = skills_data['required_skills'],
    │    preferred_skills = skills_data['preferred_skills'],
    │    analyzed_at = NOW()
    │  WHERE id = 'job-456'
    │
    ├─ 更新 task-004 状态 → success
    │
    └─ 更新 workflow 状态
       UPDATE workflow_executions SET
         status='completed',
         output_data='{"job_id": "job-456", "skills": ...}',
         completed_at=NOW()
       WHERE id='wf-001'


时间线 T0+16s: 前端接收通知
─────────────────────────────────────────────────────────
  WebSocket 连接 或 轮询 GET /api/workflows/wf-001
    │
    ▼
  浏览器收到完成通知
    {
      workflow_id: "wf-001",
      status: "completed",
      result: {
        job_id: "job-456",
        required_skills: ["Python", "FastAPI", "PostgreSQL"],
        preferred_skills: ["Docker", "AWS"],
        ...
      }
    }
    │
    └─ 刷新 UI 显示分析结果
```

**数据流转关系图**：

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  fetch_html  │─────▶│html_to_md    │─────▶│translate_job │
│              │      │              │      │              │
│ Output:      │      │ Input: html  │      │ Input: md    │
│ html_content │      │ Output: md   │      │ Output: cn   │
└──────────────┘      └──────────────┘      └──────────────┘
                                                     │
                                                     ▼
                                            ┌──────────────┐
                                            │extract_skills│
                                            │              │
                                            │ Input: cn    │
                                            │ Output: JSON │
                                            └──────────────┘
                                                     │
                                                     ▼
                                            ┌──────────────┐
                                            │  Update DB   │
                                            │  jobs table  │
                                            └──────────────┘
```

### 2.2 Application 生成工作流数据流（并行执行）

**场景**: 用户点击"生成申请材料"按钮

```
并行执行模式（Chord Pattern）：

┌─────────────────────────────────────────────────────────┐
│                  Parallel Execution                      │
│                                                          │
│   ┌──────────────────┐      ┌──────────────────┐       │
│   │ Tailor Resume    │      │ Generate Cover   │       │
│   │                  │      │ Letter           │       │
│   │ Worker 1         │      │ Worker 2         │       │
│   │ T0+0s ~ T0+12s   │      │ T0+0s ~ T0+8s    │       │
│   └────────┬─────────┘      └────────┬─────────┘       │
│            │                         │                  │
│            └────────┬────────────────┘                  │
└─────────────────────┼──────────────────────────────────┘
                      │ 等待所有并行任务完成
                      ▼
            ┌──────────────────┐
            │  Quality Check   │
            │  (Chord Callback)│
            │                  │
            │  Worker 3        │
            │  T0+12s ~ T0+15s │
            └──────────────────┘


详细数据流：

时间线 T0: 用户触发
─────────────────────────────────────────────────────────
  POST /api/applications/generate
  {
    job_id: "job-456",
    resume_id: "resume-789"
  }
    │
    ▼
  创建 workflow_executions
    {
      id: "wf-002",
      workflow_type: "application_generation",
      status: "pending"
    }
    │
    ▼
  创建 3 个 task_executions
    - task-101: tailor_resume (pending)
    - task-102: generate_cover_letter (pending)
    - task-103: quality_check (pending, depends_on: [task-101, task-102])
    │
    ▼
  构建 Celery Chord
    chord([
      tailor_resume.s("wf-002", "task-101", job_id, resume_id),
      generate_cover_letter.s("wf-002", "task-102", job_id, resume_id)
    ])(quality_check.s("wf-002", "task-103"))


时间线 T0+0s: 两个任务同时开始
─────────────────────────────────────────────────────────

  【Worker 1 - task-101】                 【Worker 2 - task-102】

  tailor_resume()                         generate_cover_letter()
    │                                       │
    ├─ 读取职位要求                         ├─ 读取职位描述
    │  job = db.query(Job).get(job_id)    │  job = db.query(Job).get(job_id)
    │                                       │
    ├─ 读取用户简历                         ├─ 读取用户信息
    │  resume = db.query(Resume)           │  user = db.query(User)
    │          .get(resume_id)             │          .get(user_id)
    │                                       │
    ├─ 调用 OpenAI Agents SDK              ├─ 调用 OpenAI Agents SDK
    │  agent = Agent(                      │  agent = Agent(
    │    name="ResumeTailor",              │    name="CoverLetterWriter",
    │    model="gpt-4o",                   │    model="gpt-4o",
    │    instructions="""                  │    instructions="""
    │      根据职位要求定制简历：             │      生成求职信：
    │      1. 突出相关技能                   │      1. 表达对职位兴趣
    │      2. 调整项目经验描述               │      2. 匹配技能说明
    │      3. 保持真实性                     │      3. 体现个人价值
    │    """                                │    """
    │  )                                   │  )
    │                                       │
    │  tailored = agent.run({              │  cover_letter = agent.run({
    │    "job": job.dict(),                │    "job": job.dict(),
    │    "resume": resume.dict()           │    "user": user.dict()
    │  })                                  │  })
    │                                       │
    ├─ 保存定制简历                         ├─ 保存求职信
    │  resume_version = ResumeVersion(     │  cover_letter_obj = CoverLetter(
    │    resume_id=resume_id,              │    application_id=app_id,
    │    job_id=job_id,                    │    content=cover_letter,
    │    content=tailored,                 │    language="zh"
    │    version_type="tailored"           │  )
    │  )                                   │  db.add(cover_letter_obj)
    │  db.add(resume_version)              │  db.commit()
    │  db.commit()                         │
    │                                       │
    ├─ 更新 task-101 → success             ├─ 更新 task-102 → success
    │  execution_time: 12000ms             │  execution_time: 8000ms
    │                                       │
    └─ 返回 resume_version_id              └─ 返回 cover_letter_id


时间线 T0+12s: 并行任务全部完成，触发 Callback
─────────────────────────────────────────────────────────

  Celery Chord Callback 自动触发
    │
    ▼
  Worker 3 - task-103: quality_check()
    │
    ├─ 接收上游结果
    │  results = [
    │    {"resume_version_id": "rv-001"},    # task-101 的返回
    │    {"cover_letter_id": "cl-001"}       # task-102 的返回
    │  ]
    │
    ├─ 更新 task-103 → running
    │
    ├─ 执行质量检查
    │  resume_version = db.query(ResumeVersion).get("rv-001")
    │  cover_letter = db.query(CoverLetter).get("cl-001")
    │
    │  # 检查逻辑
    │  issues = []
    │  if len(resume_version.content) < 500:
    │    issues.append("简历内容过短")
    │  if "Python" not in resume_version.content:
    │    issues.append("未突出关键技能")
    │
    │  quality_score = calculate_score(resume_version, cover_letter, job)
    │
    ├─ 保存质量报告
    │  UPDATE applications SET
    │    quality_score = quality_score,
    │    quality_issues = issues,
    │    status = 'ready'
    │  WHERE id = app_id
    │
    ├─ 更新 task-103 → success
    │
    └─ 更新 workflow → completed
       UPDATE workflow_executions SET
         status='completed',
         output_data={
           "resume_version_id": "rv-001",
           "cover_letter_id": "cl-001",
           "quality_score": 85
         }
       WHERE id='wf-002'


时间线 T0+15s: 前端收到通知
─────────────────────────────────────────────────────────
  WebSocket 推送或轮询获取
    {
      workflow_id: "wf-002",
      status: "completed",
      result: {
        resume_version_id: "rv-001",
        cover_letter_id: "cl-001",
        quality_score: 85,
        quality_issues: []
      }
    }
    │
    └─ 页面跳转到申请详情页
       显示定制简历和求职信
```

**并行执行时间节省**：

```
串行执行总时间: 12s (简历) + 8s (求职信) + 3s (质检) = 23s
并行执行总时间: max(12s, 8s) + 3s = 15s
节省时间: 8s (约 35%)
```

### 2.3 异常场景数据流

**场景: AI API 调用失败 + 自动重试**

```
时间线 T0: 任务开始执行
─────────────────────────────────────────────────────────
  Worker 1 执行: translate_job("wf-001", "task-003", markdown)
    │
    ├─ 更新 task-003 → running
    │
    ├─ 调用 DeepSeek API
    │  try:
    │    response = client.chat.completions.create(...)
    │  except openai.RateLimitError as e:
    │    # API 限流错误
    │    raise Retry(exc=e, countdown=60)  # 60秒后重试
    │
    ├─ 更新 task-003 状态
    │  UPDATE task_executions SET
    │    status='retry',
    │    retry_count=1,
    │    error_message='Rate limit exceeded'
    │  WHERE id='task-003'
    │
    └─ Celery 自动调度重试任务


时间线 T0+60s: 第一次重试
─────────────────────────────────────────────────────────
  Worker 2 接收重试任务
    │
    ├─ 检查重试次数
    │  task = db.query(TaskExecution).get('task-003')
    │  if task.retry_count >= task.max_retries:
    │    raise MaxRetriesExceeded()
    │
    ├─ 更新 status → running (retry_count=1)
    │
    ├─ 再次调用 API
    │  response = client.chat.completions.create(...)
    │  # 假设这次成功
    │
    ├─ 更新 task-003 → success
    │  retry_count=1 (保留重试历史)
    │
    └─ 继续执行下游任务
```

**场景: 任务失败超过最大重试次数**

```
时间线 T0+180s: 第三次重试仍然失败
─────────────────────────────────────────────────────────
  Worker 执行第 3 次重试
    │
    ├─ API 调用仍然失败
    │  except openai.APIError as e:
    │
    ├─ 检查重试次数
    │  if retry_count >= max_retries:  # 3 >= 3
    │    # 不再重试，标记失败
    │
    ├─ 更新 task-003 → failed
    │  UPDATE task_executions SET
    │    status='failed',
    │    retry_count=3,
    │    error_message='API Error after 3 retries'
    │  WHERE id='task-003'
    │
    ├─ 更新 workflow → failed
    │  UPDATE workflow_executions SET
    │    status='failed',
    │    error_message='Task task-003 failed'
    │  WHERE id='wf-001'
    │
    └─ 发送告警通知
       - WebSocket 推送给用户
       - 记录到监控系统（Sentry/CloudWatch）
       - 发送邮件给运维团队（如果是系统级错误）
```

## 3. 方案的问题与限制

### 3.1 工作流变更困难

**问题描述**：

工作流的 DAG 结构硬编码在 Python 代码中，修改流程需要改代码、测试、部署。

```python
# 当前实现（硬编码）
def create_job_analysis_workflow(job_url):
    return chain(
        fetch_html.s(job_url),
        html_to_markdown.s(),
        translate_job.s(),
        extract_skills.s()
    )

# 如果要在"翻译"和"提取技能"之间插入"内容审核"步骤
# 必须修改代码：
def create_job_analysis_workflow(job_url):
    return chain(
        fetch_html.s(job_url),
        html_to_markdown.s(),
        translate_job.s(),
        content_moderation.s(),  # 新增
        extract_skills.s()
    )
# 然后重新部署所有 worker
```

**影响**：

- 业务调整响应慢（需要开发周期）
- A/B 测试不同流程困难
- 无法支持不同用户使用不同流程版本

### 3.2 缺乏条件分支能力

**问题描述**：

Celery Canvas 原生不支持复杂的条件逻辑（if-else, switch-case）。

**示例场景**：

```
需求：如果职位描述是中文，跳过翻译步骤

理想流程：
  fetch_html → html_to_md → [检测语言]
                               ├─ 中文 → extract_skills
                               └─ 英文 → translate → extract_skills

当前实现问题：
  # Canvas 无法直接表达条件分支
  # 只能在任务内部处理，造成代码冗余

  def translate_job(markdown):
      lang = detect_language(markdown)
      if lang == 'zh':
          return markdown  # 直接返回，不翻译
      else:
          return call_deepseek_translate(markdown)

  # 问题：即使跳过翻译，任务仍会执行（浪费资源）
  # 且无法在 UI 上区分"已跳过"和"已翻译"
```

### 3.3 状态一致性风险

**问题描述**：

状态分别存储在 Celery（Redis）和 PostgreSQL 中，可能出现不一致。

**风险场景**：

```
场景 1: 数据库更新失败

  Worker 执行任务
    ├─ Celery 标记任务成功（写入 Redis）✓
    ├─ 尝试更新 PostgreSQL
    │   UPDATE task_executions SET status='success' WHERE id='task-003'
    │   # PostgreSQL 宕机或网络超时 ✗
    └─ 结果：
        - Celery 认为任务成功，触发下游任务
        - PostgreSQL 仍显示 status='running'
        - 前端轮询看到的是"运行中"，但实际已完成

场景 2: Worker 崩溃

  Worker 正在执行任务
    ├─ 更新 PostgreSQL: status='running' ✓
    ├─ 执行业务逻辑（调用 AI API）
    │   ... 执行中 ...
    │   # Worker 进程突然崩溃（OOM/服务器重启）✗
    └─ 结果：
        - PostgreSQL 显示 status='running'（永远卡住）
        - Celery 任务已丢失（Redis 中无记录）
        - 没有自动恢复机制
```

**当前缓解措施不足**：

- 没有定期扫描"僵尸任务"的机制
- 缺少 PostgreSQL ↔ Celery 的状态对账功能

### 3.4 缺乏可视化和调试工具

**问题描述**：

- Celery Flower 只能看到任务执行情况，看不到业务工作流
- 没有 DAG 可视化界面（不像 Airflow/Prefect）
- 调试困难：无法追踪某个 job 的完整执行链路

**痛点**：

```
用户反馈："我的职位分析卡住了"

运维排查过程：
  1. 查 workflow_executions 表 → 看到 status='running'
  2. 查 task_executions 表 → 找到哪个任务卡住
  3. 登录 Celery Flower → 搜索 celery_task_id
  4. 查看 Worker 日志 → 找到具体错误

理想工具：
  一个界面显示：
    [Job Analysis - wf-001]
      ├─ ✓ fetch_html (2.1s)
      ├─ ✓ html_to_md (0.8s)
      ├─ ⏳ translate_job (running 35s)  ← 点击查看详情
      └─ ⏸ extract_skills (pending)

  点击 translate_job 显示：
    - Input: markdown 内容预览
    - Worker: worker-node-2
    - Logs: 实时日志流
    - Retry History: 已重试 1 次
```

### 3.5 暂停/恢复功能缺失

**问题描述**：

无法暂停正在执行的工作流，也无法从中断点恢复。

**场景需求**：

```
场景 1: 人工审核

  期望流程：
    生成简历 → [暂停，等待用户审核] → 用户确认 → 发送申请

  当前问题：
    - Celery 任务一旦启动就会执行到底
    - 只能拆分成两个独立工作流（不优雅）

场景 2: 配额耗尽

  期望流程：
    翻译任务执行中 → 检测到 API 配额用完 → 暂停工作流 → 第二天自动恢复

  当前问题：
    - 无法暂停，只能失败或无限重试
    - 无法持久化"等待恢复"状态

场景 3: 长时间任务

  期望流程：
    批量处理 100 个职位 → 执行到 50 个时服务器需要维护 → 暂停 → 维护完成后从第 51 个继续

  当前问题：
    - Worker 重启会丢失进度
    - 无法优雅地保存断点
```

### 3.6 版本管理需求

**需求描述**：

需要支持工作流版本管理，以便：
- 记录每个执行使用的配置版本
- 支持版本切换和回滚
- 对比不同版本的性能指标

**解决方案**：

采用**简化版本管理方案**（详见 4.3 节）：
- 基于 YAML 配置文件的版本管理
- 通过 `registry.yaml` 手动切换 `active_version`
- 数据库记录每次执行的 `config_version`
- 支持版本性能对比分析

## 4. 扩展方案

### 4.1 工作流配置化

**目标**: 将工作流定义从代码移到配置文件，支持动态修改和版本管理。

#### 4.1.1 YAML 配置方案

**配置文件示例** (`workflows/job_analysis_v2.yaml`):

```yaml
workflow:
  name: job_analysis
  version: "2.0"
  description: "职位分析工作流 - 增加内容审核步骤"

  # 全局配置
  config:
    max_retries: 3
    timeout: 300  # 整个工作流超时时间（秒）

  # 任务定义
  tasks:
    - id: fetch_html
      type: api_call
      handler: tasks.scraping.fetch_html
      config:
        timeout: 30
        retry_on: [ConnectionError, Timeout]
      input:
        job_url: "{{ workflow.input.job_url }}"
      output:
        html_content: "result"

    - id: html_to_markdown
      type: data_processing
      handler: tasks.processing.html_to_markdown
      depends_on: [fetch_html]
      input:
        html: "{{ tasks.fetch_html.output.html_content }}"
      output:
        markdown: "result"

    - id: detect_language
      type: ai_agent
      handler: tasks.ai.detect_language
      depends_on: [html_to_markdown]
      input:
        text: "{{ tasks.html_to_markdown.output.markdown }}"
      output:
        language: "result.language"

    # 条件分支
    - id: translate_job
      type: ai_agent
      handler: tasks.ai.translate_to_chinese
      depends_on: [detect_language]
      condition: "{{ tasks.detect_language.output.language != 'zh' }}"  # 非中文才翻译
      input:
        text: "{{ tasks.html_to_markdown.output.markdown }}"
        model: "deepseek-chat"
      output:
        translated_text: "result"

    - id: content_moderation
      type: ai_agent
      handler: tasks.ai.moderate_content
      depends_on: [translate_job]
      config:
        optional: true  # 可选任务，失败不影响整体流程
      input:
        text: "{{ tasks.translate_job.output.translated_text or tasks.html_to_markdown.output.markdown }}"
      output:
        is_safe: "result.is_safe"
        moderation_tags: "result.tags"

    - id: extract_skills
      type: ai_agent
      handler: tasks.ai.extract_job_skills
      depends_on: [content_moderation]
      input:
        text: "{{ tasks.translate_job.output.translated_text or tasks.html_to_markdown.output.markdown }}"
        model: "gpt-4o"
      output:
        skills_data: "result"
```

#### 4.1.2 配置解析引擎

**工作流解析器** (`app/core/workflow/parser.py`):

```python
from typing import Dict, List, Any
import yaml
from jinja2 import Template

class WorkflowParser:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.workflow_name = self.config['workflow']['name']
        self.version = self.config['workflow']['version']

    def build_dag(self, input_data: Dict) -> List[Dict]:
        """构建任务 DAG"""
        tasks = []
        context = {'workflow': {'input': input_data}, 'tasks': {}}

        for task_def in self.config['tasks']:
            # 渲染输入参数（Jinja2 模板）
            rendered_input = self._render_template(task_def['input'], context)

            # 检查条件（如果有）
            if 'condition' in task_def:
                condition_result = self._evaluate_condition(task_def['condition'], context)
                if not condition_result:
                    continue  # 跳过此任务

            task = {
                'id': task_def['id'],
                'handler': task_def['handler'],
                'depends_on': task_def.get('depends_on', []),
                'input': rendered_input,
                'config': task_def.get('config', {})
            }
            tasks.append(task)

        return tasks

    def _render_template(self, template_dict: Dict, context: Dict) -> Dict:
        """渲染 Jinja2 模板"""
        result = {}
        for key, value in template_dict.items():
            if isinstance(value, str) and '{{' in value:
                template = Template(value)
                result[key] = template.render(context)
            else:
                result[key] = value
        return result
```

#### 4.1.3 动态工作流执行

**动态执行器** (`app/core/workflow/executor.py`):

```python
from celery import group, chain, chord
from .parser import WorkflowParser

class WorkflowExecutor:
    def __init__(self, workflow_name: str, version: str = "latest"):
        config_path = f"workflows/{workflow_name}_{version}.yaml"
        self.parser = WorkflowParser(config_path)

    def execute(self, workflow_id: str, input_data: Dict):
        """根据配置文件动态构建并执行工作流"""
        tasks_dag = self.parser.build_dag(input_data)

        # 构建 Celery Canvas
        celery_tasks = self._build_celery_chain(workflow_id, tasks_dag)
        celery_tasks.apply_async()

    def _build_celery_chain(self, workflow_id: str, tasks_dag: List[Dict]):
        """将 DAG 转换为 Celery Canvas"""
        task_map = {}

        for task_def in tasks_dag:
            # 动态导入任务函数
            handler = self._import_handler(task_def['handler'])

            # 创建 Celery signature
            sig = handler.s(
                workflow_id=workflow_id,
                task_id=task_def['id'],
                **task_def['input']
            )

            task_map[task_def['id']] = sig

        # 根据 depends_on 构建执行链
        return self._build_execution_chain(task_map, tasks_dag)
```

**优势**：

```
1. 快速迭代
   - 修改工作流只需编辑 YAML 文件
   - 无需重新部署代码
   - 支持热更新（重启 worker 即可）

2. 版本管理
   - job_analysis_v1.yaml
   - job_analysis_v2.yaml
   - 数据库记录使用的版本号

3. A/B 测试
   workflow_execution.config_version = random.choice(["v1", "v2"])
   executor = WorkflowExecutor("job_analysis", workflow_execution.config_version)

4. 可视化
   可以直接解析 YAML 文件生成流程图
```

### 4.2 异常恢复方案

#### 4.2.1 自动重试策略

**分层重试配置**:

```python
# 任务级别重试（Celery 原生）
@app.task(bind=True, max_retries=3, default_retry_delay=60)
def translate_job(self, workflow_id, task_id, text):
    try:
        result = call_deepseek_api(text)
        return result
    except RateLimitError as e:
        # 指数退避重试：60s, 120s, 240s
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    except APIError as e:
        if "invalid_api_key" in str(e):
            # 配置错误，不重试
            raise
        else:
            raise self.retry(exc=e)

# 工作流级别重试（自定义）
def retry_failed_workflow(workflow_id: str):
    """手动重试失败的工作流"""
    workflow = db.query(WorkflowExecution).get(workflow_id)

    if workflow.status != 'failed':
        raise ValueError("只能重试失败的工作流")

    # 找到失败的任务
    failed_tasks = db.query(TaskExecution).filter(
        TaskExecution.workflow_id == workflow_id,
        TaskExecution.status == 'failed'
    ).all()

    # 从失败点重新执行
    for task in failed_tasks:
        # 重置状态
        task.status = 'pending'
        task.retry_count = 0
        task.error_message = None
        db.commit()

        # 重新提交任务
        handler = import_string(task.task_name)
        handler.apply_async(
            args=[workflow_id, task.id, task.input_data],
            task_id=f"{task.id}-retry-{int(time.time())}"
        )
```

#### 4.2.2 僵尸任务清理

**定时任务监控**:

```python
from celery import Celery
from celery.schedules import crontab

@app.task
def cleanup_zombie_tasks():
    """每 5 分钟扫描一次僵尸任务"""
    # 查找状态为 running 但超过 10 分钟没更新的任务
    threshold = datetime.now() - timedelta(minutes=10)

    zombie_tasks = db.query(TaskExecution).filter(
        TaskExecution.status == 'running',
        TaskExecution.updated_at < threshold
    ).all()

    for task in zombie_tasks:
        # 检查 Celery 中是否还在运行
        celery_task = AsyncResult(task.celery_task_id)

        if celery_task.state == 'PENDING':
            # Celery 中已无此任务，标记为失败
            task.status = 'failed'
            task.error_message = 'Task timeout or worker crashed'
            db.commit()

            # 触发告警
            send_alert(f"Zombie task detected: {task.id}")

# 注册定时任务
app.conf.beat_schedule = {
    'cleanup-zombie-tasks': {
        'task': 'tasks.cleanup_zombie_tasks',
        'schedule': crontab(minute='*/5'),  # 每 5 分钟
    },
}
```

### 4.3 版本管理方案

#### 4.3.1 目录结构

```
backend/
├── workflows/
│   ├── job_analysis/
│   │   ├── v1.0.0.yaml
│   │   ├── v1.1.0.yaml
│   │   └── v2.0.0.yaml
│   │
│   ├── application_generation/
│   │   ├── v1.0.0.yaml
│   │   └── v1.1.0.yaml
│   │
│   └── registry.yaml              # 版本注册表
```

#### 4.3.2 版本注册表

**workflows/registry.yaml**:

```yaml
# 工作流版本注册表
workflows:
  job_analysis:
    active_version: "1.1.0"        # 当前使用的版本（手动修改这里切换版本）
    description: "职位分析工作流"

  application_generation:
    active_version: "1.0.0"
    description: "申请材料生成工作流"

  resume_tailor:
    active_version: "1.0.0"
    description: "简历定制工作流"
```

#### 4.3.3 数据库设计

```sql
-- workflow_executions 表只需要记录版本号
ALTER TABLE workflow_executions
ADD COLUMN config_version VARCHAR(20) NOT NULL DEFAULT 'v1.0.0';

-- 添加索引用于查询统计
CREATE INDEX idx_workflow_version ON workflow_executions(workflow_type, config_version, created_at);
```

#### 4.3.4 版本加载器

**app/core/workflow/version_loader.py**:

```python
import yaml
from pathlib import Path
from typing import Dict, Optional
from functools import lru_cache

class WorkflowVersionLoader:
    """工作流版本加载器"""

    def __init__(self, workflows_dir: str = "workflows"):
        self.workflows_dir = Path(workflows_dir)
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict:
        """加载版本注册表"""
        registry_path = self.workflows_dir / "registry.yaml"
        with open(registry_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_active_version(self, workflow_type: str) -> str:
        """获取当前激活的版本"""
        if workflow_type not in self.registry['workflows']:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        return self.registry['workflows'][workflow_type]['active_version']

    @lru_cache(maxsize=32)
    def load_workflow_config(self, workflow_type: str, version: Optional[str] = None) -> Dict:
        """
        加载工作流配置

        Args:
            workflow_type: 工作流类型
            version: 指定版本，如果为 None 则使用 active_version
        """
        if version is None:
            version = self.get_active_version(workflow_type)

        config_path = self.workflows_dir / workflow_type / f"{version}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Workflow config not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config

    def reload_registry(self):
        """重新加载注册表（用于配置变更后热更新）"""
        self.registry = self._load_registry()
        # 清除缓存
        self.load_workflow_config.cache_clear()


# 全局单例
_loader = None

def get_version_loader() -> WorkflowVersionLoader:
    """获取版本加载器单例"""
    global _loader
    if _loader is None:
        _loader = WorkflowVersionLoader()
    return _loader
```

#### 4.3.5 工作流执行器集成

**app/core/workflow/executor.py**:

```python
from .version_loader import get_version_loader
from .parser import WorkflowParser

class WorkflowExecutor:
    """工作流执行器"""

    def __init__(self, workflow_type: str, version: Optional[str] = None):
        """
        初始化执行器

        Args:
            workflow_type: 工作流类型
            version: 指定版本（可选），不指定则使用 registry 中的 active_version
        """
        self.workflow_type = workflow_type
        self.loader = get_version_loader()

        # 如果没有指定版本，使用 active_version
        if version is None:
            self.version = self.loader.get_active_version(workflow_type)
        else:
            self.version = version

        # 加载配置
        self.config = self.loader.load_workflow_config(workflow_type, self.version)
        self.parser = WorkflowParser(self.config)

    def execute(self, workflow_id: str, input_data: Dict):
        """执行工作流"""
        # 构建任务 DAG
        tasks_dag = self.parser.build_dag(input_data)

        # 构建并执行 Celery Canvas
        celery_tasks = self._build_celery_chain(workflow_id, tasks_dag)
        celery_tasks.apply_async()

    def _build_celery_chain(self, workflow_id: str, tasks_dag: List[Dict]):
        """将 DAG 转换为 Celery Canvas"""
        # ... 实现逻辑
        pass
```

#### 4.3.6 API 集成

**app/modules/jobs/router.py**:

```python
from app.core.workflow.executor import WorkflowExecutor
from app.core.workflow.version_loader import get_version_loader

@router.post("/jobs/analyze")
async def analyze_job(
    request: AnalyzeJobRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分析职位"""

    # 检查配额
    if not check_user_quota(user):
        raise HTTPException(403, "AI 分析次数已用完")

    # 获取当前激活版本
    loader = get_version_loader()
    active_version = loader.get_active_version("job_analysis")

    # 创建工作流记录
    workflow = WorkflowExecution(
        workflow_type="job_analysis",
        config_version=active_version,  # 记录使用的版本
        user_id=user.id,
        entity_id=request.job_id,
        status="pending",
        input_data=request.dict()
    )
    db.add(workflow)
    db.commit()

    # 执行工作流（会自动使用 active_version）
    executor = WorkflowExecutor("job_analysis")
    executor.execute(str(workflow.id), request.dict())

    return {
        "workflow_id": str(workflow.id),
        "version": active_version,
        "status": "running"
    }
```

#### 4.3.7 版本切换流程

**步骤 1: 修改配置文件**

```yaml
# 编辑 workflows/registry.yaml

workflows:
  job_analysis:
    active_version: "2.0.0"  # 从 1.1.0 改为 2.0.0
    description: "职位分析工作流"
```

**步骤 2: 热更新配置（可选）**

```python
# 方式 1: 提供管理 API（需要管理员权限）
@router.post("/admin/workflows/reload-config")
async def reload_workflow_config(
    admin: User = Depends(require_admin)
):
    """重新加载工作流配置"""
    loader = get_version_loader()
    loader.reload_registry()
    return {"message": "Configuration reloaded"}

# 方式 2: 重启 Worker 进程
# supervisorctl restart celery_worker
```

**步骤 3: 验证切换**

```sql
-- 查询最近创建的工作流使用的版本
SELECT config_version, COUNT(*) as count
FROM workflow_executions
WHERE workflow_type = 'job_analysis'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY config_version;

-- 预期结果：
-- config_version | count
-- ---------------+-------
-- 2.0.0          | 15     <- 新创建的都是 2.0.0
-- 1.1.0          | 3      <- 旧的可能还在执行中
```

#### 4.3.8 版本对比分析

**app/modules/admin/analytics.py**:

```python
def compare_workflow_versions(
    workflow_type: str,
    version_a: str,
    version_b: str,
    days: int = 7
):
    """对比两个版本的性能"""

    since = datetime.now() - timedelta(days=days)

    result = db.query(
        WorkflowExecution.config_version,
        func.count().label('total'),
        func.sum(
            case((WorkflowExecution.status == 'completed', 1), else_=0)
        ).label('success'),
        func.avg(
            extract('epoch', WorkflowExecution.completed_at - WorkflowExecution.created_at)
        ).label('avg_duration')
    ).filter(
        WorkflowExecution.workflow_type == workflow_type,
        WorkflowExecution.config_version.in_([version_a, version_b]),
        WorkflowExecution.created_at >= since
    ).group_by(
        WorkflowExecution.config_version
    ).all()

    comparison = {}
    for row in result:
        comparison[row.config_version] = {
            'total': row.total,
            'success': row.success,
            'success_rate': (row.success / row.total * 100) if row.total > 0 else 0,
            'avg_duration': float(row.avg_duration) if row.avg_duration else 0
        }

    return comparison

# 使用示例
stats = compare_workflow_versions("job_analysis", "1.1.0", "2.0.0", days=7)
# {
#     "1.1.0": {"total": 8520, "success": 8102, "success_rate": 95.1, "avg_duration": 12.3},
#     "2.0.0": {"total": 950, "success": 912, "success_rate": 96.0, "avg_duration": 10.8}
# }
```

## 5. 实施建议

### 5.1 初期实施（推荐方案）

**核心组件**：
- Celery Canvas + PostgreSQL 状态表（任务编排和状态持久化）
- YAML 配置文件 + 版本注册表（工作流定义和版本管理）
- 基础监控（Celery Flower + 数据库查询）

**实施步骤**：

1. **搭建基础架构**
   - 配置 PostgreSQL 数据库（创建 workflow_executions 和 task_executions 表）
   - 部署 Redis（Celery broker）
   - 启动 Celery Workers

2. **创建工作流配置**
   - 创建 `workflows/` 目录结构
   - 编写初始版本的 YAML 配置文件（v1.0.0）
   - 配置 `registry.yaml` 注册表

3. **实现核心模块**
   - 开发 `WorkflowVersionLoader`（版本加载器）
   - 开发 `WorkflowParser`（配置解析器）
   - 开发 `WorkflowExecutor`（执行器）

4. **集成 API**
   - 在业务 API 中集成工作流执行
   - 实现状态查询接口
   - 添加版本对比分析功能

**优势**：
- 简单直接，易于理解和维护
- 支持版本管理和性能对比
- 修改工作流只需编辑 YAML 文件
- 回滚简单（修改 registry.yaml 即可）

### 5.2 监控和运维

**基础监控**：
- Celery Flower（任务执行监控）
- PostgreSQL 查询（工作流状态统计）
- 日志聚合（ELK/Loki）

**告警机制**：
- 僵尸任务检测（定时扫描长时间未更新的任务）
- 失败率告警（超过阈值时通知）
- 队列积压告警（任务堆积监控）

**性能优化**：
- 定期清理历史数据（归档旧的执行记录）
- 优化任务粒度（避免过粗或过细）
- 调整 Worker 并发数（根据负载动态调整）

### 5.3 未来扩展

**何时考虑升级**：

如果出现以下情况，可考虑升级到更复杂的工作流引擎（如 Temporal.io 或 Prefect）：
- 需要复杂的条件分支和循环逻辑
- 需要人工审核节点（暂停/恢复工作流）
- 工作流定义变更非常频繁（每周多次）
- 需要可视化的 DAG 编辑器

**当前方案适用场景**：
- 工作流结构相对稳定
- 主要是串行和简单并行（chain/chord）
- 团队规模中小型（< 20 人）
- 重视简洁性和可维护性
