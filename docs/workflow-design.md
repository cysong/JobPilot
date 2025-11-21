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

### 3.6 版本管理和灰度发布困难

**问题描述**：

工作流定义在代码中，无法同时运行多个版本。

**问题场景**：

```
场景：优化了简历定制算法，想对 10% 用户灰度测试

期望：
  - 90% 用户使用 v1 算法（旧版）
  - 10% 用户使用 v2 算法（新版）
  - 对比两个版本的质量分数

当前实现困难：
  # 代码中只能有一个实现
  def tailor_resume(job, resume):
      # 用 v1 还是 v2？
      if random.random() < 0.1:
          return tailor_resume_v2(job, resume)  # 新算法
      else:
          return tailor_resume_v1(job, resume)  # 旧算法

  问题：
    - 代码混乱（v1/v2 逻辑混在一起）
    - 无法追溯"这个简历用的是哪个版本"
    - 回滚困难（需要再次部署代码）
```

### 3.7 任务粒度难以平衡

**问题描述**：

任务粒度太粗或太细都有问题。

**粒度太粗的问题**：

```python
# 将整个流程放在一个任务里
def analyze_job_all_in_one(job_url):
    html = fetch_html(job_url)
    md = html_to_markdown(html)
    translated = translate(md)
    skills = extract_skills(translated)
    return skills

问题：
  - 任务执行时间长（15s+），容易超时
  - 失败后重试成本高（所有步骤重新执行）
  - 无法并行化
  - 难以定位具体哪一步出错
```

**粒度太细的问题**：

```python
# 每个小步骤都是一个任务
chain(
    fetch_html.s(url),
    extract_title.s(),        # 提取标题
    extract_company.s(),      # 提取公司
    extract_salary.s(),       # 提取薪资
    extract_location.s(),     # 提取地点
    extract_description.s(),  # 提取描述
    ...
)

问题：
  - 任务数量爆炸（单个工作流 20+ 任务）
  - Celery 调度开销大
  - 任务间数据传递频繁（Redis I/O 压力）
  - workflow_executions 表记录膨胀
```

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

### 4.3 流程变更管理

#### 4.3.1 向后兼容的版本升级

**场景**: 在工作流中间插入新步骤

```yaml
# workflows/job_analysis_v1.yaml（旧版）
tasks:
  - id: fetch_html
  - id: html_to_markdown
  - id: translate_job
  - id: extract_skills

# workflows/job_analysis_v2.yaml（新版，插入审核步骤）
tasks:
  - id: fetch_html
  - id: html_to_markdown
  - id: translate_job
  - id: content_moderation    # 新增
    config:
      optional: true           # 标记为可选，兼容旧版
  - id: extract_skills
```

**数据库迁移**:

```sql
-- 添加版本字段
ALTER TABLE workflow_executions ADD COLUMN config_version VARCHAR(20) DEFAULT 'v1';

-- 创建工作流版本表
CREATE TABLE workflow_versions (
    id UUID PRIMARY KEY,
    workflow_type VARCHAR(50),
    version VARCHAR(20),
    config_yaml TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP,
    UNIQUE(workflow_type, version)
);
```

**版本路由逻辑**:

```python
def create_workflow(workflow_type: str, user_id: str, input_data: Dict):
    # 根据用户或实验分组选择版本
    version = get_workflow_version_for_user(user_id, workflow_type)

    workflow = WorkflowExecution(
        workflow_type=workflow_type,
        config_version=version,
        user_id=user_id,
        input_data=input_data
    )
    db.add(workflow)
    db.commit()

    # 使用对应版本的配置执行
    executor = WorkflowExecutor(workflow_type, version)
    executor.execute(workflow.id, input_data)

def get_workflow_version_for_user(user_id: str, workflow_type: str) -> str:
    """根据实验分组返回版本"""
    user = db.query(User).get(user_id)

    # 实验分组逻辑
    if user.experiment_group == 'control':
        return 'v1'
    elif user.experiment_group == 'treatment':
        return 'v2'
    else:
        # 默认使用最新稳定版本
        latest_version = db.query(WorkflowVersion).filter(
            WorkflowVersion.workflow_type == workflow_type,
            WorkflowVersion.is_active == True
        ).order_by(WorkflowVersion.created_at.desc()).first()
        return latest_version.version
```

#### 4.3.2 灰度发布

**灰度发布策略**:

```python
class WorkflowVersionRouter:
    def __init__(self):
        self.rollout_config = {
            'job_analysis': {
                'v1': {'weight': 90, 'max_users': None},      # 90% 流量
                'v2': {'weight': 10, 'max_users': 1000}       # 10% 流量，最多 1000 用户
            }
        }

    def select_version(self, workflow_type: str, user_id: str) -> str:
        config = self.rollout_config.get(workflow_type, {})

        # 检查用户是否已固定版本（保证一致性）
        user_version = redis.get(f"user_workflow_version:{user_id}:{workflow_type}")
        if user_version:
            return user_version

        # 基于用户 ID 哈希的一致性路由
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100

        cumulative_weight = 0
        for version, settings in config.items():
            cumulative_weight += settings['weight']
            if user_hash < cumulative_weight:
                # 检查版本用户数限制
                if settings['max_users']:
                    version_users = redis.scard(f"workflow_version_users:{workflow_type}:{version}")
                    if version_users >= settings['max_users']:
                        continue  # 超过限制，尝试下一个版本

                # 记录用户版本（7 天过期）
                redis.setex(f"user_workflow_version:{user_id}:{workflow_type}", 604800, version)
                redis.sadd(f"workflow_version_users:{workflow_type}:{version}", user_id)
                return version

        return 'v1'  # 默认版本
```

## 5. 实施建议

### 5.1 MVP 阶段（0-3 个月）

**采用方案**：
- 基础 Celery Canvas + PostgreSQL 状态表
- 硬编码工作流定义
- 基础监控（Flower + 数据库查询）

**理由**：
- 快速上线，验证业务模型
- 工作流相对稳定，变更少
- 团队规模小，沟通成本低

### 5.2 成长阶段（3-12 个月）

**优化重点**：
1. 实施 YAML 配置化（工作流配置化）
2. 部署 Prometheus + Grafana（监控）
3. 集成 Sentry（错误追踪）
4. 实现僵尸任务清理（异常恢复）

**收益**：
- 支持 A/B 测试不同工作流
- 可视化监控降低运维成本
- 提高系统稳定性

### 5.3 成熟阶段（12 个月后）

**考虑迁移**：

如果出现以下情况，考虑迁移到 Temporal.io 或 Prefect：
- 工作流变更频繁（每周多次）
- 需要复杂条件分支和循环
- 需要人工审核节点（暂停/恢复）
- 团队规模扩大（多个团队并行开发工作流）

**迁移成本**：
- 2-3 个开发月
- 需要重写所有工作流定义
- 需要迁移历史数据
