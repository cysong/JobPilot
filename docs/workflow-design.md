# JobPilot 工作流系统设计方案

## 1. 系统概述

### 1.1 架构定位

JobPilot 采用 **Celery Canvas + PostgreSQL 状态机 + Outbox Pattern** 的混合架构:

- **Celery Canvas**: 负责任务编排和分布式执行 (chain, group, chord)
- **PostgreSQL**: 作为唯一数据源 (Single Source of Truth)，负责持久化状态跟踪
- **Outbox Pattern**: 保证事件可靠发布，解决双写问题
- **Spec-kit Gateway**: 统一 AI 调用层，作为内部模块/库 (非独立服务)

### 1.2 调用链路

```
┌─────────────────────────────────────────────────────────────────┐
│                       Frontend (React)                           │
│  • 用户交互  • WebSocket 接收实时通知                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/REST
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                           │
│  • Router: 路由和参数验证                                         │
│  • Middleware: 认证、限流、日志                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Service Layer (业务逻辑)                        │
│  • ApplicationService: 应用业务逻辑                               │
│  • WorkflowService: 工作流编排                                    │
│  • 事务控制 + Outbox 事件写入                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                Repository Layer (数据访问)                        │
│  • ApplicationRepo  • WorkflowRepo  • TaskRepo  • OutboxRepo    │
│  • 封装查询逻辑  • 提供事务友好接口                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Database (PostgreSQL)                            │
│  • applications  • workflow_executions  • task_executions        │
│  • outbox_events  • ai_calls  • documents                       │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────── Outbox Consumer ────────┐
                    │ (Celery Beat: 每 5 秒轮询)       │
                    │  • 批量获取未发布事件             │
                    │  • 并发处理 (Semaphore 限制)    │
                    │  • 独立 session (避免竞态)       │
                    └──────────┬──────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
    ┌─────────────────────┐       ┌───────────────────────┐
    │  Event Handler      │       │  Celery Worker        │
    │  • 工作流初始化      │       │  • 执行任务           │
    │  • 状态更新通知      │       │  • AI 调用            │
    │  • 配额扣减         │       │  • 状态持久化         │
    └─────────────────────┘       └──────────┬────────────┘
                                              │
                                              ▼
                                   ┌────────────────────┐
                                   │  Spec-kit Gateway  │
                                   │  • Prompt 渲染     │
                                   │  • Model 路由      │
                                   │  • 使用量记录      │
                                   └──────────┬─────────┘
                                              │
                                              ▼
                                   ┌────────────────────┐
                                   │   LLM Providers    │
                                   │  • DeepSeek        │
                                   │  • OpenAI          │
                                   └────────────────────┘
```

## 2. 核心组件设计

### 2.1 工作流系统

#### 2.1.1 数据库设计

**workflow_executions 表** (工作流执行记录):

```sql
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_type VARCHAR(50) NOT NULL,         -- 'job_analysis', 'application_generation'
    config_version VARCHAR(20) NOT NULL,         -- 工作流配置版本 (如 'v1.0.0')
    user_id UUID NOT NULL REFERENCES users(id),
    entity_id UUID,                              -- job_id 或 application_id
    status VARCHAR(20) NOT NULL,                 -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    celery_task_id VARCHAR(255),                 -- Celery Chain 根任务 ID
    input_data JSONB NOT NULL,                   -- 输入参数
    output_data JSONB,                           -- 输出结果
    error_message TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_workflow_user_status ON workflow_executions(user_id, status);
CREATE INDEX idx_workflow_type_status ON workflow_executions(workflow_type, status);
CREATE INDEX idx_workflow_version ON workflow_executions(workflow_type, config_version, created_at);
```

**task_executions 表** (任务执行记录):

```sql
CREATE TABLE task_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow_executions(id) ON DELETE CASCADE,
    task_name VARCHAR(100) NOT NULL,             -- 'fetch_html', 'translate_job', etc.
    task_type VARCHAR(50),                       -- 'ai_agent', 'data_processing', 'api_call'
    priority VARCHAR(20) DEFAULT 'normal',       -- 'high', 'normal', 'low'
    status VARCHAR(20) NOT NULL,                 -- 'pending', 'running', 'success', 'failed', 'retry'
    celery_task_id VARCHAR(255),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    execution_time_ms INT,                       -- 执行耗时 (毫秒)
    worker_id VARCHAR(100),                      -- 执行该任务的 worker
    depends_on JSONB,                            -- 依赖的任务 ID 列表 ['task_id_1', 'task_id_2']
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_task_workflow_status ON task_executions(workflow_id, status);
CREATE INDEX idx_task_name ON task_executions(task_name);
CREATE INDEX idx_task_priority ON task_executions(priority, status, created_at);
```

#### 2.1.2 YAML 配置示例

**目录结构**:

```
backend/
├── workflows/
│   ├── job_analysis/
│   │   ├── v1.0.0.yaml
│   │   └── v1.1.0.yaml
│   ├── application_generation/
│   │   └── v1.0.0.yaml
│   └── registry.yaml              # 版本注册表
```

**workflows/job_analysis/v1.1.0.yaml**:

```yaml
workflow:
  name: job_analysis
  version: "1.1.0"
  description: "Job analysis workflow with language detection and conditional translation"

  config:
    max_retries: 3
    timeout: 300  # seconds

  tasks:
    - id: fetch_html
      type: api_call
      handler: tasks.scraping.fetch_html
      priority: normal
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
        prompt_id: "language_detector"
        prompt_version: "v1.0.0"  # Decoupled from config_version
      output:
        language: "result.language"

    - id: translate_job
      type: ai_agent
      handler: tasks.ai.translate_to_chinese
      depends_on: [detect_language]
      condition: "{{ tasks.detect_language.output.language != 'zh' }}"  # Skip if Chinese
      input:
        text: "{{ tasks.html_to_markdown.output.markdown }}"
        prompt_id: "job_translator"
        prompt_version: "v1.0.0"
        model: "deepseek-chat"
      output:
        translated_text: "result"

    - id: extract_skills
      type: ai_agent
      handler: tasks.ai.extract_job_skills
      depends_on: [translate_job]
      priority: high  # Higher priority for final step
      input:
        text: "{{ tasks.translate_job.output.translated_text or tasks.html_to_markdown.output.markdown }}"
        prompt_id: "skill_extractor"
        prompt_version: "v2.0.0"  # Can use different prompt version
        model: "gpt-4o"
      output:
        skills_data: "result"
```

**workflows/registry.yaml** (版本注册表):

```yaml
# Workflow version registry
# Modify active_version here to switch versions globally

workflows:
  job_analysis:
    active_version: "1.1.0"        # Change this to switch versions
    description: "Job analysis workflow"
    available_versions:
      - "1.0.0"
      - "1.1.0"

  application_generation:
    active_version: "1.0.0"
    description: "Application material generation workflow"
    available_versions:
      - "1.0.0"
```

#### 2.1.3 Repository 模式

**职责分离**:

采用 Repository 模式实现数据访问层与业务逻辑层的解耦:

- **Router Layer**: 路由和参数验证
- **Service Layer**: 业务逻辑、事务控制、事件编排
- **Repository Layer**: 数据访问封装、查询构建
- **Model Layer**: 数据模型定义

**核心 Repository**:

```
ApplicationRepository    - 应用数据 CRUD 和查询
WorkflowRepository      - 工作流状态管理
TaskRepository          - 任务记录管理
OutboxRepository        - 事件队列管理
```

**接口设计** (关键方法):

```python
class ApplicationRepository:
    @staticmethod
    async def create(db, application) -> Application
    @staticmethod
    async def get_by_user_and_job(db, user_id, job_id) -> Optional[Application]
    @staticmethod
    async def mark_ready(db, application, cover_letter_document_id)
    @staticmethod
    async def mark_failed(db, application, error)

class WorkflowRepository:
    @staticmethod
    async def create(db, workflow_type, user_id, entity_id, input_data)
    @staticmethod
    async def mark_running(db, workflow, celery_task_id)
    @staticmethod
    async def mark_completed(db, workflow, output_data)
    @staticmethod
    async def reset_for_retry(db, workflow)

class OutboxRepository:
    @staticmethod
    async def enqueue_event(db, event_type, aggregate_id, payload, meta)
    @staticmethod
    async def fetch_pending_batch(db, batch_size) -> List[OutboxEvent]
    @staticmethod
    async def mark_published(db, event)
    @staticmethod
    async def mark_retry(db, event, error_message)
```

**优势**:

- ✅ 测试友好: Service 层可独立单元测试
- ✅ 查询复用: 复杂查询统一封装
- ✅ 事务安全: Repository 方法都是事务友好的
- ✅ 易于维护: 数据访问逻辑集中管理

### 2.2 Outbox Pattern (事件可靠发布)

#### 2.2.1 核心概念

Outbox Pattern 解决 PostgreSQL 与 Celery (Redis) 的双写问题:

- **问题**: 业务逻辑需要同时更新 PostgreSQL (业务数据) 和发送通知/邮件，如果一方失败会导致数据不一致
- **解决**: 所有状态变更在同一事务中写入 PostgreSQL，包括 `outbox_events` 表，后台异步发布事件

#### 2.2.2 数据库设计

```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,            -- 'task_started', 'task_completed', 'workflow_failed', etc.
    aggregate_type VARCHAR(50) NOT NULL,         -- 'task', 'workflow', 'application'
    aggregate_id VARCHAR(255) NOT NULL,          -- task_id, workflow_id, etc.
    payload JSONB NOT NULL,                      -- Event data
    published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    next_retry_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB                               -- Additional context (user_id, etc.)
);

CREATE INDEX idx_outbox_unpublished ON outbox_events(published, created_at) WHERE published = FALSE;
CREATE INDEX idx_outbox_retry ON outbox_events(next_retry_at) WHERE published = FALSE AND next_retry_at IS NOT NULL;
CREATE INDEX idx_outbox_aggregate ON outbox_events(aggregate_type, aggregate_id, created_at);
```

#### 2.2.3 事件发布流程

**核心原则**: 所有状态变更与 Outbox 事件在同一事务中提交,保证原子性。

**事件写入** (使用 Repository 模式):

```python
# API Layer: 创建应用 + 写入事件
async def create_application(db, user, payload):
    async with db.begin():
        # 1. 创建 Application
        application = Application(...)
        await ApplicationRepository.create(db, application)

        # 2. 写入 Outbox 事件 (同一事务)
        await OutboxRepository.enqueue_event(
            db,
            event_type="application_created",
            aggregate_id=application.id,
            payload=ApplicationCreatedPayload(...).model_dump(),
            meta={"user_id": user.id}
        )
        # 原子提交: 应用 + 事件都持久化或都失败

    return application

# Celery Worker: 任务执行中写入事件
async def generate_cover_letter_task(application_id, workflow_id):
    async with db.begin():
        # 更新状态 + 写入事件
        await WorkflowRepository.mark_running(db, workflow)
        await OutboxRepository.enqueue_event(
            db, event_type="workflow_started", ...
        )

    # 执行业务逻辑 (事务外)
    result = await ai_service.generate_cover_letter(...)

    async with db.begin():
        # 保存结果 + 写入完成事件
        await save_document(db, result)
        await WorkflowRepository.mark_completed(db, workflow)
        await OutboxRepository.enqueue_event(
            db, event_type="workflow_completed", ...
        )
```

**事件类型和 Payload**:

```python
# event_types.py
class ApplicationEventType(str, Enum):
    APPLICATION_CREATED = "application_created"
    APPLICATION_READY = "application_ready"
    APPLICATION_FAILED = "application_failed"

class ApplicationCreatedPayload(BaseModel):
    application_id: str
    user_id: int
    job_id: int
    resume_document_id: str
    is_retry: bool = False
```

#### 2.2.4 并发消费优化

**核心机制**:
- 使用 `asyncio.Semaphore` 限制并发数为 5
- 每个事件独立 session，避免竞争
- 批量拉取 + 并发处理，提升 5 倍吞吐

**配置**:
- `OUTBOX_MAX_CONCURRENT`: 5 (最大并发事件处理数)
- `OUTBOX_BATCH_SIZE`: 100 (单次拉取事件数)
- `OUTBOX_CONSUMER_INTERVAL_SECONDS`: 5.0 (Celery 轮询间隔)

**并发消费实现**:

```python
async def process_outbox_batch(db: AsyncSession, *, batch_size: int = 100):
    """Fetch and process events with controlled concurrency."""
    # 1. Batch fetch pending events (skip locked)
    events = await OutboxRepository.fetch_pending_batch(db, batch_size)
    if not events:
        return

    # 2. Concurrent processing with Semaphore
    semaphore = asyncio.Semaphore(app_module_settings.OUTBOX_MAX_CONCURRENT)

    async def process_single(event: OutboxEvent):
        async with semaphore:
            async with async_session_factory() as event_db:  # Independent session
                handler = HANDLERS[event.event_type]
                await handler(event_db, event)
                await OutboxRepository.mark_published(event_db, event)
                await event_db.commit()

    await asyncio.gather(*[process_single(e) for e in events], return_exceptions=True)
```

**事件处理器注册**:

```python
HANDLERS = {
    "application_created": handle_application_created,    # Init workflow
    "application_ready": handle_application_ready,        # Send notifications
    "workflow_failed": handle_workflow_failed,            # Error handling
}
```

### 2.3 配置管理

#### 2.3.1 模块级配置

使用 Pydantic Settings 管理 applications 模块配置:

```python
class ApplicationModuleSettings(BaseSettings):
    # Outbox 消费配置
    OUTBOX_BATCH_SIZE: int = 100
    OUTBOX_MAX_CONCURRENT: int = 5              # 最大并发事件处理数
    OUTBOX_CONSUMER_INTERVAL_SECONDS: float = 5.0  # 轮询间隔

    # 工作流配置
    WORKFLOW_VERSION: str = "v1.0.0"
    COVER_LETTER_PROMPT_ID: str = "cover_letter_v1"
    COVER_LETTER_MODEL: str = "deepseek-chat"

    class Config:
        env_prefix = "APP_MODULE_"              # 环境变量前缀
```

#### 2.3.2 环境变量覆盖

通过 `.env` 文件或环境变量覆盖默认配置:

```bash
# Outbox 并发控制
APP_MODULE_OUTBOX_MAX_CONCURRENT=10
APP_MODULE_OUTBOX_BATCH_SIZE=200

# 工作流版本
APP_MODULE_WORKFLOW_VERSION=v1.1.0

# AI 模型选择
APP_MODULE_COVER_LETTER_MODEL=gpt-4o
```

#### 2.3.3 配置使用

```python
from app.modules.applications.config import app_module_settings

# 在 outbox consumer 中使用
max_concurrent = app_module_settings.OUTBOX_MAX_CONCURRENT
batch_size = app_module_settings.OUTBOX_BATCH_SIZE

# 在 service 中使用
model = app_module_settings.COVER_LETTER_MODEL
```

**优势**:

- ✅ 集中管理: 所有配置在一个文件
- ✅ 类型安全: Pydantic 自动验证
- ✅ 环境隔离: 开发/生产环境不同配置
- ✅ 易于调优: 运行时调整无需改代码

### 2.4 Spec-kit Gateway (统一 AI 调用层)

#### 2.4.1 定位

Spec-kit Gateway 作为**内部模块/库** (非独立服务)，提供:

- 统一的 Prompt 管理和渲染
- 多模型路由和策略
- AI 调用记录 (异步写入 `ai_calls` 表 via Outbox Pattern)
- 重试和超时策略

#### 2.4.2 Prompt 管理 (与 config_version 解耦)

**目录结构**:

```
backend/
├── app/
│   └── modules/
│       └── ai_agent/
│           └── prompts/
│               ├── manifest.yaml              # Prompt registry
│               ├── job_analysis/
│               │   ├── language_detector_v1.0.0.md
│               │   ├── job_translator_v1.0.0.md
│               │   └── skill_extractor_v2.0.0.md
│               └── resume_tailor/
│                   └── tailor_light_v1.0.0.md
```

**prompts/manifest.yaml**:

```yaml
# Prompt version registry
# prompt_version is DECOUPLED from workflow config_version
# Same config_version can use different prompt_version for A/B testing

prompts:
  - id: language_detector
    version: "v1.0.0"
    model_default: "deepseek-chat"
    path: "job_analysis/language_detector_v1.0.0.md"
    variables:
      - name: text
        type: string
        required: true
    output_format: json

  - id: job_translator
    version: "v1.0.0"
    model_default: "deepseek-chat"
    path: "job_analysis/job_translator_v1.0.0.md"
    variables:
      - name: text
        type: string
        required: true
      - name: target_language
        type: string
        required: false
        default: "zh"

  - id: skill_extractor
    version: "v2.0.0"  # New version with improved prompts
    model_default: "gpt-4o"
    path: "job_analysis/skill_extractor_v2.0.0.md"
    variables:
      - name: job_description
        type: string
        required: true
    output_format: json

  - id: skill_extractor
    version: "v1.0.0"  # Old version (kept for rollback)
    model_default: "gpt-4o"
    path: "job_analysis/skill_extractor_v1.0.0.md"
    variables:
      - name: job_description
        type: string
        required: true
    output_format: json
```

**Prompt Store** (app/core/spec_kit/prompt_store.py):

```python
class PromptStore:
    """Prompt template store with version management (decoupled from workflow config_version)"""

    def __init__(self, prompts_dir: str = "app/modules/ai_agent/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.manifest = self._load_manifest()  # Load prompts/manifest.yaml

    def render_prompt(self, prompt_id: str, prompt_version: str, variables: Dict) -> Dict:
        """Render Jinja2 template with variables, returns rendered_text + metadata"""
        prompt_def = self._find_prompt(prompt_id, prompt_version)
        self._validate_variables(prompt_def, variables)  # Check required vars

        template_path = self.prompts_dir / prompt_def['path']
        rendered = Template(template_path.read_text()).render(**variables)

        return {
            "rendered_text": rendered,
            "model_default": prompt_def.get('model_default'),
            "output_format": prompt_def.get('output_format', 'text')
        }
```

#### 2.4.3 Gateway 实现

**核心流程**: Prompt 渲染 → LLM 调用 → Outbox 记录

```python
class SpecKitGateway:
    def call(self, prompt_id: str, prompt_version: str, variables: Dict,
             model: Optional[str] = None, db_session = None, **context) -> Dict:
        # 1. Render prompt template
        rendered = self.prompt_store.render_prompt(prompt_id, prompt_version, variables)
        model_to_use = model or rendered['model_default']

        # 2. Call LLM with retry/timeout
        try:
            response = self.llm_client.call(
                model=model_to_use,
                prompt=rendered['rendered_text'],
                timeout=60, max_retries=2
            )
            status = "success"
        except Exception as e:
            status = self._classify_error(e)  # 'ratelimit', 'timeout', 'error'
            self._log_ai_call(db_session, status=status, error=str(e), **context)
            raise

        # 3. Async log via Outbox (written to ai_calls table by consumer)
        self._log_ai_call(db_session, status="success", usage=response['usage'], **context)
        return response
```

**调用示例**:

```python
result = gateway.call(
    prompt_id="language_detector",
    prompt_version="v1.0.0",
    variables={"text": markdown},
    model="deepseek-chat",
    db_session=db,
    workflow_id=workflow_id,
    task_id=task_id
)
```

#### 2.4.4 AI Calls 表设计

```sql
CREATE TABLE ai_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    workflow_execution_id UUID REFERENCES workflow_executions(id) ON DELETE SET NULL,
    task_id UUID REFERENCES task_executions(id) ON DELETE SET NULL,
    operation VARCHAR(100),                      -- 'job_analysis', 'resume_tailor', 'cover_letter'
    prompt_id VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(20) NOT NULL,
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(50),                        -- 'deepseek', 'openai'
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    cache_read_tokens INT DEFAULT 0,             -- Prompt caching tokens read
    cache_write_tokens INT DEFAULT 0,            -- Prompt caching tokens written
    estimated_cost DECIMAL(10, 6) DEFAULT 0,
    latency_ms INT,
    status VARCHAR(20) NOT NULL,                 -- 'success', 'timeout', 'ratelimit', 'error'
    retry_count INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ai_calls_workflow ON ai_calls(workflow_execution_id, task_id);
CREATE INDEX idx_ai_calls_operation ON ai_calls(operation, created_at);
CREATE INDEX idx_ai_calls_prompt ON ai_calls(prompt_id, prompt_version, created_at);
CREATE INDEX idx_ai_calls_model ON ai_calls(model, created_at);
CREATE INDEX idx_ai_calls_status ON ai_calls(status, created_at);
CREATE INDEX idx_ai_calls_user ON ai_calls(user_id, created_at);
```

**Outbox Handler 注册**:

```python
# Outbox consumer 通过 ai_call_completed 事件异步写入 ai_calls 表
HANDLERS = {
    "ai_call_completed": handle_ai_call_completed,  # Write to ai_calls table
    "application_created": handle_application_created,
    "application_ready": handle_application_ready,
}
```

### 2.5 任务优先级与配额系统

#### 2.5.1 优先级队列

**三级优先级**: `high`, `normal` (default), `low`

**Celery 配置** (app/core/celery_app.py):

```python
from celery import Celery

app = Celery('jobpilot')

app.conf.task_routes = {
    # High priority tasks
    'tasks.ai.extract_skills': {'queue': 'high_priority'},
    'tasks.ai.quality_check': {'queue': 'high_priority'},

    # Normal priority tasks (default)
    'tasks.ai.translate_job': {'queue': 'normal_priority'},
    'tasks.ai.tailor_resume': {'queue': 'normal_priority'},

    # Low priority tasks
    'tasks.processing.html_to_markdown': {'queue': 'low_priority'},
    'tasks.scraping.fetch_html': {'queue': 'low_priority'},
}

# Worker configuration
# celery -A app.core.celery_app worker -Q high_priority,normal_priority,low_priority
```

**动态优先级** (在 YAML 配置中指定):

```yaml
tasks:
  - id: extract_skills
    priority: high  # Override default priority
    # ...
```

#### 2.5.2 配额管理

**用户配额表** (users 表扩展):

```sql
ALTER TABLE users ADD COLUMN daily_job_limit INT DEFAULT 50;
ALTER TABLE users ADD COLUMN daily_token_limit INT DEFAULT 100000;
ALTER TABLE users ADD COLUMN jobs_analyzed_today INT DEFAULT 0;
ALTER TABLE users ADD COLUMN tokens_used_today INT DEFAULT 0;
ALTER TABLE users ADD COLUMN quota_reset_at TIMESTAMP DEFAULT NOW();
```

**配额检查** (API 层):

```python
@router.post("/jobs/analyze")
async def analyze_job(
    request: AnalyzeJobRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check quota before creating workflow
    if not UserQuotaService.check_quota(user):
        raise HTTPException(
            status_code=403,
            detail="Daily quota exceeded. Please upgrade your plan or wait until tomorrow."
        )

    # Create workflow...
```

**配额扣减** (via Outbox after task success):

```python
def update_quota(event: OutboxEvent):
    """
    Deduct quota AFTER task success
    Called by Outbox Publisher when ai_call_completed event is processed
    """
    from app.modules.users.service import UserQuotaService

    user_id = event.metadata.get("user_id")
    if not user_id:
        return

    # Only deduct for successful calls
    if event.payload.get("status") != "success":
        return

    tokens_used = (
        event.payload.get("input_tokens", 0) +
        event.payload.get("output_tokens", 0)
    )

    operation = event.payload.get("operation")

    UserQuotaService.deduct_quota(
        user_id=user_id,
        tokens=tokens_used,
        operation=operation
    )
```

## 3. 数据流详解

### 3.1 Job 分析工作流完整流程

```
用户点击 → API 请求 → 创建工作流 → Celery 执行 → Outbox 发布事件 → 前端通知

时间线 T0: 用户触发
─────────────────────────────────────────────────────────
  浏览器
    │ POST /api/jobs/analyze { job_url: "..." }
    ▼
  FastAPI Server
    │
    ├─ 检查用户配额 (UserQuotaService.check_quota)
    │
    ├─ 获取 active_version from registry.yaml
    │  loader = WorkflowVersionLoader()
    │  active_version = loader.get_active_version("job_analysis")  # "1.1.0"
    │
    ├─ BEGIN TRANSACTION
    │  │
    │  ├─ 创建 workflow_executions 记录
    │  │  {
    │  │    id: "wf-001",
    │  │    workflow_type: "job_analysis",
    │  │    config_version: "1.1.0",  # From registry
    │  │    user_id: "user-123",
    │  │    status: "pending",
    │  │    input_data: { job_url: "..." }
    │  │  }
    │  │
    │  ├─ 创建 task_executions 记录 (预占位)
    │  │  - task-001: fetch_html (pending, priority: normal)
    │  │  - task-002: html_to_markdown (pending, depends_on: [task-001])
    │  │  - task-003: detect_language (pending, depends_on: [task-002])
    │  │  - task-004: translate_job (pending, depends_on: [task-003])
    │  │  - task-005: extract_skills (pending, depends_on: [task-004], priority: high)
    │  │
    │  └─ 写入 outbox_events
    │     {
    │       event_type: "workflow_created",
    │       aggregate_type: "workflow",
    │       aggregate_id: "wf-001",
    │       payload: { workflow_id: "wf-001", status: "pending" }
    │     }
    │
    ├─ COMMIT TRANSACTION
    │
    ├─ 加载工作流配置并构建 Celery Chain
    │  executor = WorkflowExecutor("job_analysis", version="1.1.0")
    │  executor.execute(workflow_id="wf-001", input_data={...})
    │
    │  → Celery Chain:
    │    chain(
    │      fetch_html.s("wf-001", "task-001", job_url),
    │      html_to_markdown.s("wf-001", "task-002"),
    │      detect_language.s("wf-001", "task-003"),
    │      translate_job.s("wf-001", "task-004"),  # May be skipped by condition
    │      extract_skills.s("wf-001", "task-005")
    │    ).apply_async(queue='normal_priority')
    │
    └─ 返回响应
       {
         workflow_id: "wf-001",
         version: "1.1.0",
         status: "running"
       }


时间线 T0+2s: Worker 1 执行 fetch_html
─────────────────────────────────────────────────────────
  Celery Worker 1 (normal_priority queue)
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-001 状态
    │  │  UPDATE task_executions SET
    │  │    status='running',
    │  │    started_at=NOW(),
    │  │    worker_id='worker-node-1'
    │  │  WHERE id='task-001'
    │  │
    │  └─ 写入 outbox_events
    │     event_type: "task_started"
    │     aggregate_id: "task-001"
    │
    ├─ COMMIT TRANSACTION
    │
    ├─ 执行爬取逻辑 (business logic outside transaction)
    │  result = httpx.get(job_url, timeout=30)
    │  html_content = result.text
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-001 状态
    │  │  UPDATE task_executions SET
    │  │    status='success',
    │  │    output_data='{"html": "..."}',
    │  │    execution_time_ms=1850,
    │  │    completed_at=NOW()
    │  │  WHERE id='task-001'
    │  │
    │  └─ 写入 outbox_events
    │     event_type: "task_completed"
    │     aggregate_id: "task-001"
    │
    ├─ COMMIT TRANSACTION
    │
    └─ 返回 html_content (传递给下一个任务)


时间线 T0+10s: Worker 2 执行 detect_language (AI 调用)
─────────────────────────────────────────────────────────
  Celery Worker 2
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-003 → running
    │  └─ 写入 outbox_events (task_started)
    │
    ├─ COMMIT
    │
    ├─ 调用 Spec-kit Gateway
    │  from app.core.spec_kit import SpecKitGateway
    │
    │  gateway = SpecKitGateway()
    │  result = gateway.call(
    │    prompt_id="language_detector",
    │    prompt_version="v1.0.0",  # From YAML config (decoupled)
    │    variables={"text": markdown},
    │    model="deepseek-chat",  # Can override
    │    workflow_id="wf-001",
    │    task_id="task-003",
    │    user_id="user-123",
    │    operation="job_analysis",
    │    db_session=db  # For Outbox event writing
    │  )
    │
    │  # Gateway internally:
    │  # 1. Renders prompt from template
    │  # 2. Calls LLM (DeepSeek)
    │  # 3. Writes outbox_events (ai_call_completed) in same transaction
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-003 → success
    │  │  output_data = {"language": result["result"]["language"]}
    │  │
    │  └─ 写入 outbox_events (task_completed)
    │
    ├─ COMMIT
    │
    └─ 返回 {"language": "en"}


时间线 T0+12s: Worker 3 执行 translate_job (条件执行)
─────────────────────────────────────────────────────────
  Celery Worker 3
    │
    ├─ 检查 condition from YAML config
    │  condition: "{{ tasks.detect_language.output.language != 'zh' }}"
    │  language = "en" → Condition TRUE → Execute task
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-004 → running
    │  └─ 写入 outbox_events
    │
    ├─ COMMIT
    │
    ├─ 调用 Spec-kit Gateway
    │  result = gateway.call(
    │    prompt_id="job_translator",
    │    prompt_version="v1.0.0",
    │    variables={"text": markdown, "target_language": "zh"},
    │    model="deepseek-chat",
    │    ...
    │  )
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-004 → success
    │  └─ 写入 outbox_events
    │
    ├─ COMMIT
    │
    └─ 返回 translated_text


时间线 T0+25s: Worker 1 执行 extract_skills (HIGH priority)
─────────────────────────────────────────────────────────
  Celery Worker 1 (high_priority queue)
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-005 → running
    │  └─ 写入 outbox_events
    │
    ├─ COMMIT
    │
    ├─ 调用 Spec-kit Gateway
    │  result = gateway.call(
    │    prompt_id="skill_extractor",
    │    prompt_version="v2.0.0",  # Can use different version!
    │    variables={"job_description": translated_text},
    │    model="gpt-4o",
    │    ...
    │  )
    │
    │  # Returns JSON:
    │  # {
    │  #   "required_skills": ["Python", "FastAPI", "PostgreSQL"],
    │  #   "preferred_skills": ["Docker", "AWS"],
    │  #   "education": "Bachelor's in CS",
    │  #   "experience_years": 3
    │  # }
    │
    ├─ 保存提取结果到 jobs 表
    │  UPDATE jobs SET
    │    required_skills = result["required_skills"],
    │    preferred_skills = result["preferred_skills"],
    │    education = result["education"],
    │    experience_years = result["experience_years"],
    │    analyzed_at = NOW()
    │  WHERE id = 'job-456'
    │
    ├─ BEGIN TRANSACTION
    │  ├─ 更新 task-005 → success
    │  │
    │  ├─ 更新 workflow → completed
    │  │  UPDATE workflow_executions SET
    │  │    status='completed',
    │  │    output_data='{"job_id": "job-456", "skills": ...}',
    │  │    completed_at=NOW()
    │  │  WHERE id='wf-001'
    │  │
    │  └─ 写入 outbox_events
    │     - task_completed (task-005)
    │     - workflow_completed (wf-001)
    │
    ├─ COMMIT
    │
    └─ 工作流完成


时间线 T0+26s: Outbox Consumer 并发处理事件
─────────────────────────────────────────────────────────
  Celery Beat Task (每 5 秒触发: applications.run_outbox_consumer)
    │
    ├─ 批量拉取待处理事件
    │  events = OutboxRepository.fetch_pending_batch(db, batch_size=100)
    │  # SELECT ... WHERE published=FALSE ORDER BY created_at
    │  # LIMIT 100 FOR UPDATE SKIP LOCKED
    │
    ├─ 并发处理 (最多 5 个同时执行)
    │  Semaphore(max=5) 控制并发
    │
    │  [并发槽位 1] workflow_completed 事件
    │     → 独立 session: async_session_factory()
    │     → Handler: handle_workflow_completed
    │     → Action: 发送 WebSocket 通知
    │     → Mark published=TRUE, COMMIT
    │
    │  [并发槽位 2] task_completed 事件 (task-001)
    │     → 独立 session: async_session_factory()
    │     → Handler: handle_task_completed
    │     → Action: 发送 WebSocket 通知
    │     → Mark published=TRUE, COMMIT
    │
    │  [并发槽位 3] task_completed 事件 (task-002)
    │     → 独立 session: async_session_factory()
    │     → Handler: handle_task_completed
    │     → Mark published=TRUE, COMMIT
    │
    │  [并发槽位 4] application_created 事件
    │     → 独立 session: async_session_factory()
    │     → Handler: handle_application_created
    │     → Action: 初始化 workflow (WorkflowService.init_workflow)
    │     → Mark published=TRUE, COMMIT
    │
    │  [并发槽位 5] application_ready 事件
    │     → 独立 session: async_session_factory()
    │     → Handler: handle_application_ready
    │     → Action: 发送邮件通知
    │     → Mark published=TRUE, COMMIT
    │
    └─ await asyncio.gather() → 全部完成


时间线 T0+27s: 前端收到通知
─────────────────────────────────────────────────────────
  浏览器 (WebSocket 连接)
    │
    ├─ 接收消息:
    │  {
    │    type: "workflow_completed",
    │    workflow_id: "wf-001",
    │    status: "completed",
    │    result: {
    │      job_id: "job-456",
    │      required_skills: ["Python", "FastAPI", "PostgreSQL"],
    │      preferred_skills: ["Docker", "AWS"],
    │      ...
    │    }
    │  }
    │
    └─ 刷新 UI 显示分析结果
```

### 3.2 Application 生成工作流 (并行执行)

```
并行执行模式 (Chord Pattern):

┌─────────────────────────────────────────────────────────┐
│                  Parallel Execution                      │
│                                                          │
│   ┌──────────────────┐      ┌──────────────────┐       │
│   │ Tailor Resume    │      │ Generate Cover   │       │
│   │                  │      │ Letter           │       │
│   │ Worker 1         │      │ Worker 2         │       │
│   │ T0+0s ~ T0+12s   │      │ T0+0s ~ T0+8s    │       │
│   │ Priority: normal │      │ Priority: normal │       │
│   └────────┬─────────┘      └────────┬─────────┘       │
│            │                         │                  │
│            └────────┬────────────────┘                  │
└─────────────────────┼──────────────────────────────────┘
                      │ 等待所有并行任务完成
                      ▼
            ┌──────────────────┐
            │  Quality Check   │
            │  (Chord Callback)│
            │  Priority: high  │
            │  Worker 3        │
            │  T0+12s ~ T0+15s │
            └──────────────────┘

Celery Chord 构建:

chord([
  tailor_resume.s("wf-002", "task-101", job_id, resume_id),
  generate_cover_letter.s("wf-002", "task-102", job_id, resume_id)
])(quality_check.s("wf-002", "task-103"))

执行流程:

1. 两个任务同时提交到 normal_priority 队列
2. 空闲 Workers 并行执行
3. 两个任务都完成后,Celery 自动触发 Callback (quality_check)
4. Callback 提交到 high_priority 队列

时间节省:
  串行: 12s + 8s + 3s = 23s
  并行: max(12s, 8s) + 3s = 15s
  节省: 35%
```

## 4. 可观测性 (Observability)

### 4.1 日志策略

#### 4.1.1 结构化日志

**日志级别**:
- `INFO`: 关键业务事件 (workflow/task 状态变更)
- `WARNING`: 可恢复错误 (重试成功)
- `ERROR`: 不可恢复错误 (需要人工介入)

**关键日志点**:

```python
# Workflow lifecycle
logger.info("Workflow initialized", extra={
    "workflow_id": workflow_id,
    "workflow_type": "job_analysis",
    "config_version": "1.1.0",
    "user_id": user_id
})

# Task execution
logger.info("Task started", extra={
    "task_id": task_id,
    "task_type": "extract_skills",
    "workflow_id": workflow_id
})

# Outbox processing
logger.info("Outbox batch processed", extra={
    "batch_size": 100,
    "processed": 95,
    "failed": 5,
    "duration_ms": 4200
})

# AI Gateway
logger.info("AI call completed", extra={
    "prompt_id": "language_detector",
    "model": "deepseek-chat",
    "latency_ms": 850,
    "input_tokens": 1200,
    "output_tokens": 50
})
```

#### 4.1.2 关联 ID (Correlation ID)

每个请求携带 `X-Request-ID`，贯穿整个调用链：

```python
# API Layer
request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
logger = logger.bind(request_id=request_id)

# Pass to workflow
workflow_execution.metadata = {"request_id": request_id}

# Celery tasks inherit request_id from workflow context
```

### 4.2 性能监控

#### 4.2.1 关键指标

**Workflow 级别**:
- Workflow 执行时长分布 (p50, p95, p99)
- Workflow 成功率 (按 type 分组)
- Workflow 失败原因分布

**Task 级别**:
- Task 执行时长 (按 task_type 分组)
- Task 重试率
- Task 队列等待时长

**AI 调用级别**:
- AI call 延迟 (按 model 分组)
- Token 消耗速率 (input/output)
- AI call 错误率 (ratelimit, timeout, error)

**Outbox 级别**:
- Outbox 消费延迟 (事件创建到发布的时长)
- Outbox 积压量 (未发布事件数)
- Outbox 消费吞吐 (events/sec)

#### 4.2.2 监控查询示例

```sql
-- Workflow 成功率 (最近 24 小时)
SELECT workflow_type,
       COUNT(*) as total,
       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success,
       ROUND(100.0 * SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM workflow_executions
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY workflow_type;

-- AI call 成本统计 (按 operation)
SELECT operation,
       COUNT(*) as total_calls,
       SUM(input_tokens) as total_input_tokens,
       SUM(output_tokens) as total_output_tokens,
       SUM(estimated_cost) as total_cost
FROM ai_calls
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY operation
ORDER BY total_cost DESC;

-- Outbox 积压监控
SELECT COUNT(*) as pending_events,
       MIN(created_at) as oldest_event_time,
       EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) as max_delay_seconds
FROM outbox_events
WHERE published = FALSE;
```

### 4.3 告警规则

**高优先级告警**:
- Outbox 积压 > 1000 events 或最老事件 > 5 分钟
- Workflow 失败率 > 10% (过去 1 小时)
- AI call 错误率 > 20% (过去 10 分钟)

**中优先级告警**:
- Workflow p95 延迟 > 阈值 (job_analysis: 60s, resume_tailor: 30s)
- Task 重试率 > 15%
- User quota 接近耗尽 (剩余 < 10%)

## 5. 版本管理与切换

### 5.1 版本切换流程

**步骤 1: 修改 registry.yaml**

```yaml
# workflows/registry.yaml

workflows:
  job_analysis:
    active_version: "1.1.0"  # 从 1.0.0 切换到 1.1.0
    description: "Job analysis workflow"
```

**步骤 2: 热更新 (可选)**

```python
# 方式 1: 管理 API
@router.post("/admin/workflows/reload-config")
async def reload_workflow_config(admin: User = Depends(require_admin)):
    loader = get_version_loader()
    loader.reload_registry()
    return {"message": "Configuration reloaded"}

# 方式 2: 重启 Workers
# supervisorctl restart celery_worker
```

**步骤 3: 验证**

```sql
-- 查询最近创建的工作流版本分布
SELECT config_version, COUNT(*) as count
FROM workflow_executions
WHERE workflow_type = 'job_analysis'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY config_version;

-- 预期结果:
-- config_version | count
-- ---------------+-------
-- 1.1.0          | 42     <- 新版本
-- 1.0.0          | 5      <- 旧版本 (可能还在执行中)
```

### 5.2 Prompt 版本切换 (独立于 config_version)

**场景**: 在同一个 workflow config_version 下 A/B 测试不同 prompt 版本

**YAML 配置**:

```yaml
# workflows/job_analysis/v1.1.0.yaml (config_version 不变)

tasks:
  - id: extract_skills
    type: ai_agent
    handler: tasks.ai.extract_job_skills
    input:
      prompt_id: "skill_extractor"
      prompt_version: "v2.0.0"  # 从 v1.0.0 切换到 v2.0.0
      # ...
```

**灰度策略** (在代码中实现):

```python
# 在任务执行时动态选择 prompt_version
import random

def extract_skills(workflow_id, task_id, job_description):
    # A/B testing: 50% use v2.0.0, 50% use v1.0.0
    prompt_version = random.choice(["v2.0.0", "v1.0.0"])

    result = gateway.call(
        prompt_id="skill_extractor",
        prompt_version=prompt_version,  # Dynamic version
        variables={"job_description": job_description},
        ...
    )

    # prompt_version 会被记录到 ai_calls 表
```

**对比分析**:

```sql
-- 对比两个 prompt 版本的性能
SELECT
  prompt_version,
  COUNT(*) as total_calls,
  AVG(latency_ms) as avg_latency,
  SUM(input_tokens + output_tokens) as total_tokens,
  SUM(estimated_cost) as total_cost,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
FROM ai_calls
WHERE prompt_id = 'skill_extractor'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY prompt_version;

-- 结果示例:
-- prompt_version | total_calls | avg_latency | total_tokens | total_cost | success_rate
-- ---------------+-------------+-------------+--------------+------------+-------------
-- v1.0.0         | 523         | 2150        | 125000       | 2.50       | 94.5
-- v2.0.0         | 501         | 1890        | 98000        | 1.96       | 96.8
-- → v2.0.0 性能更优,可以全量切换
```

### 5.3 版本回滚

**场景**: 发现新版本有问题,需要快速回滚

**步骤**:

1. 修改 registry.yaml (workflow config)

```yaml
workflows:
  job_analysis:
    active_version: "1.0.0"  # 回滚到旧版本
```

2. 修改 YAML 配置 (prompt version)

```yaml
# workflows/job_analysis/v1.1.0.yaml
tasks:
  - id: extract_skills
    input:
      prompt_version: "v1.0.0"  # 回滚 prompt
```

3. 重新加载配置

```python
loader.reload_registry()
```

4. 新创建的工作流会自动使用回滚后的版本

## 5. 任务幂等性与独立性

### 5.1 幂等性策略

**创建任务前检查存在性** (无需 idempotency_key):

```python
@router.post("/jobs/analyze")
async def analyze_job(request: AnalyzeJobRequest, user: User, db: Session):
    # Check if workflow already exists for this job
    existing_workflow = db.query(WorkflowExecution).filter(
        WorkflowExecution.workflow_type == "job_analysis",
        WorkflowExecution.entity_id == request.job_id,
        WorkflowExecution.user_id == user.id,
        WorkflowExecution.status.in_(['pending', 'running'])
    ).first()

    if existing_workflow:
        return {
            "workflow_id": str(existing_workflow.id),
            "status": existing_workflow.status,
            "message": "Workflow already exists"
        }

    # Create new workflow if not exists
    workflow = WorkflowExecution(...)
    db.add(workflow)
    db.commit()

    executor.execute(workflow.id, ...)
```

### 5.2 任务独立性

**设计原则**: 保持任务独立,避免复杂工作流编排

- ✅ **推荐**: 简单的串行 (chain) 和并行 (chord) 组合
- ❌ **避免**: 复杂的嵌套、循环、长时间等待

**长时间任务处理**:

- 用户自己通过进程控制管理
- 任务之间保持独立
- 不在工作流内处理长时间等待

## 6. 实施建议

### 6.1 初期实施 (推荐)

**阶段 1: 基础架构** (Week 1-2)

1. PostgreSQL 表创建 (workflow_executions, task_executions, outbox_events)
2. Celery + Redis 配置
3. WorkflowVersionLoader + Parser + Executor 实现
4. 基础 YAML 配置 (job_analysis v1.0.0)

**阶段 2: Outbox Pattern** (Week 3)

1. OutboxEventPublisher 实现
2. OutboxPublisherDaemon 后台进程
3. 基础事件处理器 (通知、邮件)
4. 集成到任务执行流程

**阶段 3: Spec-kit Gateway** (Week 4-5)

1. PromptStore + Manifest 实现
2. Gateway + LLMClient 实现
3. AI Calls 表和异步写入
4. 集成到 AI 任务

**阶段 4: 优先级和配额** (Week 6)

1. 三级优先级队列配置
2. 用户配额管理
3. 配额检查和扣减

**阶段 5: 监控和优化** (Week 7+)

1. 性能监控和分析
2. 版本对比和 A/B 测试
3. 异常处理和告警

### 6.2 监控和运维

**基础监控**:

- Celery Flower (任务执行)
- PostgreSQL 慢查询日志
- 定时清理历史数据

**告警**:

- 僵尸任务检测 (status='running' 超过 10 分钟)
- 失败率告警 (>5%)
- 队列积压告警 (pending tasks >100)
- 配额耗尽通知

**数据清理**:

```sql
-- 归档 30 天前的已完成工作流
INSERT INTO workflow_executions_archive
SELECT * FROM workflow_executions
WHERE status IN ('completed', 'failed', 'cancelled')
  AND completed_at < NOW() - INTERVAL '30 days';

DELETE FROM workflow_executions
WHERE status IN ('completed', 'failed', 'cancelled')
  AND completed_at < NOW() - INTERVAL '30 days';

-- 清理 outbox_events (已发布且超过 7 天)
DELETE FROM outbox_events
WHERE published = TRUE
  AND published_at < NOW() - INTERVAL '7 days';
```

## 7. 未解决问题

### 7.1 暂停/恢复功能

**问题描述**:

- 当前 Celery 任务一旦启动就会执行到底,无法暂停
- 无法支持人工审核节点 (需要暂停工作流等待用户确认)
- 配额耗尽或 API 限流时,无法暂停工作流并在稍后自动恢复
- Worker 重启会丢失进度,无法从断点恢复

**影响场景**:

- 需要人工审核的工作流 (如生成简历后等待用户确认再发送申请)
- 长时间批处理任务 (如批量处理 100 个职位)
- API 配额用尽需要等待重置的场景

### 7.2 可视化调试工具

**问题描述**:

- 缺少 DAG 可视化界面 (不像 Airflow/Prefect)
- 无法直观追踪某个 job 的完整执行链路
- 调试困难,需要查询多个系统 (PostgreSQL + Celery Flower + Logs)

**期望功能**:

- 工作流执行可视化 (显示任务依赖关系和执行状态)
- 实时日志流
- 重试历史展示
- 性能分析 (任务耗时、瓶颈识别)

### 7.3 复杂条件分支

**问题描述**:

- 当前 YAML 配置仅支持简单的条件判断 (单个 `condition` 表达式)
- 无法支持复杂的 if-else, switch-case 逻辑
- 无法动态调整后续任务的参数

**限制示例**:

```yaml
# 当前支持:
condition: "{{ tasks.detect_language.output.language != 'zh' }}"

# 不支持:
# - 多条件组合: (lang != 'zh' AND confidence > 0.8)
# - 动态参数: 根据前置任务结果选择不同的 prompt_version
# - 复杂分支: switch-case 路由到不同的任务子集
```

### 7.4 跨工作流依赖

**问题描述**:

- 当前每个工作流独立执行,无法表达工作流之间的依赖关系
- 无法实现"工作流 A 完成后自动触发工作流 B"

**场景需求**:

- Job 分析完成后自动触发 Application 生成
- 批量任务的父子关系 (父任务分发子任务并汇总结果)

### 7.5 实时性能优化

**问题描述**:

- 当前性能监控基于数据库事后查询
- 无法实时识别性能瓶颈
- 缺少自动扩容/缩容机制

**期望功能**:

- 实时任务耗时监控
- 队列深度告警
- Worker 自动扩容 (基于队列积压)
- 慢任务自动降级

### 7.6 AI 调用缓存

**问题描述**:

- 当前相同输入的 AI 调用不缓存结果
- 可能导致重复调用和成本浪费

**潜在场景**:

- 用户多次分析同一个 Job
- 相同的简历定制请求

**权衡**:

- 缓存可以节省成本,但增加复杂度
- 需要考虑缓存失效策略 (prompt 版本变更、模型更新)
- 当前决策: 暂不实现,待观察实际使用模式后再决定

---

**文档版本**: v1.0.0
**最后更新**: 2025-01-22
**状态**: 最终设计稿
