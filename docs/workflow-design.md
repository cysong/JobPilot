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
┌────────────────────────────────────────────────────────────────┐
│                    Frontend (React)                             │
│  • 用户交互                                                      │
│  • WebSocket 接收实时通知                                        │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│                  API Layer (FastAPI)                            │
│  • 接收请求并验证                                                │
│  • 检查用户配额                                                  │
│  • 创建 workflow_executions 和 task_executions 记录             │
│  • 写入 outbox_events                                           │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│           Workflow Orchestration Layer                          │
│  • WorkflowVersionLoader: 加载配置版本                          │
│  • WorkflowParser: 解析 YAML 配置                              │
│  • WorkflowExecutor: 构建 Celery Canvas DAG                    │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│              Execution Layer (Celery Workers)                   │
│  • 执行具体任务                                                  │
│  • 更新 PostgreSQL 状态                                         │
│  • 写入 outbox_events                                           │
│  • 通过 Spec-kit Gateway 调用 AI                                │
└────────┬──────────────────────────────┬────────────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────┐          ┌─────────────────────────┐
│  Spec-kit Gateway│          │  Outbox Publisher       │
│  • Prompt 渲染    │          │  • 扫描未发布事件        │
│  • Model 路由     │          │  • 执行事件处理器        │
│  • 异步写 AiCalls│          │  • 发送通知/邮件         │
└────────┬─────────┘          └─────────────────────────┘
         │
         ▼
┌──────────────────┐
│  LLM Providers   │
│  • DeepSeek      │
│  • OpenAI        │
└──────────────────┘
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

**任务执行中的事件写入** (app/tasks/ai_agent.py):

```python
from app.core.outbox import OutboxEventPublisher

@celery_app.task(bind=True)
def tailor_resume(self, workflow_id, task_id, application_id, resume_id, job_id):
    # Start transaction
    with db.begin():
        # 1. Update task status
        task = db.query(TaskExecution).get(task_id)
        task.status = "running"
        task.started_at = datetime.utcnow()

        # 2. Write outbox event (in same transaction)
        OutboxEventPublisher.publish(
            db_session=db,
            event_type="task_started",
            aggregate_type="task",
            aggregate_id=task_id,
            payload={
                "task_id": task_id,
                "task_name": "tailor_resume",
                "workflow_id": workflow_id,
                "status": "running"
            },
            metadata={"user_id": task.workflow.user_id}
        )
        # Atomic commit - both task status and outbox event are persisted

    # Execute business logic (outside transaction)
    try:
        # Call AI via Spec-kit Gateway
        result = ai_agent_service.tailor_resume(
            resume_id=resume_id,
            job_id=job_id,
            prompt_version="v1.0.0"  # Decoupled from workflow config_version
        )

        # Save results (another transaction)
        with db.begin():
            # Save resume version
            resume_version = ResumeVersion(
                resume_id=resume_id,
                job_id=job_id,
                content=result.tailored_content,
                version_type="tailored"
            )
            db.add(resume_version)

            # Update task status
            task.status = "success"
            task.output_data = {"resume_version_id": str(resume_version.id)}
            task.completed_at = datetime.utcnow()
            task.execution_time_ms = (datetime.utcnow() - task.started_at).total_seconds() * 1000

            # Write completion event
            OutboxEventPublisher.publish(
                db_session=db,
                event_type="task_completed",
                aggregate_type="task",
                aggregate_id=task_id,
                payload={
                    "task_id": task_id,
                    "status": "success",
                    "output": task.output_data
                }
            )

        return {"resume_version_id": str(resume_version.id)}

    except Exception as e:
        # Handle failure
        with db.begin():
            task.status = "failed"
            task.error_message = str(e)

            OutboxEventPublisher.publish(
                db_session=db,
                event_type="task_failed",
                aggregate_type="task",
                aggregate_id=task_id,
                payload={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
        raise
```

**Outbox Publisher Daemon** (app/core/outbox/publisher.py):

```python
import time
from datetime import datetime, timedelta
from typing import Dict, Callable

class OutboxPublisherDaemon:
    """
    Background daemon that processes outbox events
    Run as a separate process or Celery Beat task
    """

    def __init__(self, db_session_factory, poll_interval: int = 5):
        self.db_factory = db_session_factory
        self.poll_interval = poll_interval
        self.handlers: Dict[str, Callable] = {}

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register event handlers for different event types"""
        from .handlers import (
            send_task_notification,
            send_workflow_notification,
            send_application_ready_email,
            update_quota
        )

        self.handlers = {
            "task_completed": send_task_notification,
            "workflow_completed": send_workflow_notification,
            "application_ready": send_application_ready_email,
            "ai_call_completed": update_quota  # Deduct quota after success
        }

    def run(self):
        """Main event loop"""
        while True:
            try:
                self._process_batch(batch_size=100)
            except Exception as e:
                logger.error(f"Outbox publisher error: {e}")

            time.sleep(self.poll_interval)

    def _process_batch(self, batch_size: int):
        """Process a batch of unpublished events"""
        db = self.db_factory()

        try:
            # Fetch unpublished events
            events = db.query(OutboxEvent).filter(
                OutboxEvent.published == False,
                OutboxEvent.retry_count < OutboxEvent.max_retries,
                or_(
                    OutboxEvent.next_retry_at == None,
                    OutboxEvent.next_retry_at <= datetime.utcnow()
                )
            ).order_by(
                OutboxEvent.created_at
            ).limit(batch_size).with_for_update(skip_locked=True).all()

            for event in events:
                self._process_event(db, event)

            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Batch processing error: {e}")
        finally:
            db.close()

    def _process_event(self, db, event: OutboxEvent):
        """Process a single event"""
        handler = self.handlers.get(event.event_type)

        if not handler:
            logger.warning(f"No handler for event type: {event.event_type}")
            event.published = True
            event.published_at = datetime.utcnow()
            return

        try:
            # Execute handler
            handler(event)

            # Mark as published
            event.published = True
            event.published_at = datetime.utcnow()

        except Exception as e:
            # Retry with exponential backoff
            event.retry_count += 1
            event.error_message = str(e)

            if event.retry_count < event.max_retries:
                # Exponential backoff: 60s, 120s, 240s
                delay_seconds = 60 * (2 ** event.retry_count)
                event.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            else:
                # Max retries exceeded
                logger.error(f"Event {event.id} failed after {event.retry_count} retries: {e}")
                event.published = True  # Stop retrying
                event.published_at = datetime.utcnow()
```

**Event Handlers** (app/core/outbox/handlers.py):

```python
def send_task_notification(event: OutboxEvent):
    """Send WebSocket notification for task completion"""
    from app.core.websocket import broadcast_to_user

    user_id = event.metadata.get("user_id")
    if not user_id:
        return

    broadcast_to_user(
        user_id=user_id,
        message={
            "type": "task_update",
            "task_id": event.aggregate_id,
            "status": event.payload.get("status"),
            "output": event.payload.get("output")
        }
    )

def send_application_ready_email(event: OutboxEvent):
    """Send email notification when application is ready"""
    from app.core.email import send_email

    application_id = event.aggregate_id
    user_email = event.metadata.get("user_email")

    send_email(
        to=user_email,
        subject="Your application materials are ready",
        template="application_ready",
        context={
            "application_id": application_id,
            "application_url": f"https://jobpilot.com/applications/{application_id}"
        }
    )

def update_quota(event: OutboxEvent):
    """Deduct user quota after successful AI call"""
    from app.modules.users.service import UserQuotaService

    user_id = event.metadata.get("user_id")
    tokens_used = event.payload.get("total_tokens", 0)

    UserQuotaService.deduct_quota(
        user_id=user_id,
        tokens=tokens_used,
        operation=event.payload.get("operation")
    )
```

### 2.3 Spec-kit Gateway (统一 AI 调用层)

#### 2.3.1 定位

Spec-kit Gateway 作为**内部模块/库** (非独立服务)，提供:

- 统一的 Prompt 管理和渲染
- 多模型路由和策略
- AI 调用记录 (异步写入 `ai_calls` 表 via Outbox Pattern)
- 重试和超时策略

#### 2.3.2 Prompt 管理 (与 config_version 解耦)

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
import yaml
from pathlib import Path
from jinja2 import Template, UndefinedError
from typing import Dict, Optional

class PromptStore:
    """
    Prompt template store with version management
    Decoupled from workflow config_version
    """

    def __init__(self, prompts_dir: str = "app/modules/ai_agent/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict:
        """Load prompt manifest"""
        manifest_path = self.prompts_dir / "manifest.yaml"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def render_prompt(
        self,
        prompt_id: str,
        prompt_version: str,
        variables: Dict
    ) -> Dict:
        """
        Render prompt template with variables

        Returns:
            {
                "prompt_id": str,
                "prompt_version": str,
                "rendered_text": str,
                "model_default": str,
                "output_format": str
            }
        """
        # Find prompt definition
        prompt_def = self._find_prompt(prompt_id, prompt_version)
        if not prompt_def:
            raise ValueError(f"Prompt not found: {prompt_id}@{prompt_version}")

        # Validate variables
        self._validate_variables(prompt_def, variables)

        # Load template file
        template_path = self.prompts_dir / prompt_def['path']
        with open(template_path, 'r', encoding='utf-8') as f:
            template_text = f.read()

        # Render template
        try:
            template = Template(template_text)
            rendered = template.render(**variables)
        except UndefinedError as e:
            raise ValueError(f"Template rendering failed: {e}")

        return {
            "prompt_id": prompt_id,
            "prompt_version": prompt_version,
            "rendered_text": rendered,
            "model_default": prompt_def.get('model_default'),
            "output_format": prompt_def.get('output_format', 'text')
        }

    def _find_prompt(self, prompt_id: str, version: str) -> Optional[Dict]:
        """Find prompt definition by ID and version"""
        for prompt in self.manifest['prompts']:
            if prompt['id'] == prompt_id and prompt['version'] == version:
                return prompt
        return None

    def _validate_variables(self, prompt_def: Dict, variables: Dict):
        """Validate that all required variables are provided"""
        required_vars = [
            var['name'] for var in prompt_def.get('variables', [])
            if var.get('required', False)
        ]

        missing_vars = set(required_vars) - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")

        # Check for unexpected variables
        defined_vars = [var['name'] for var in prompt_def.get('variables', [])]
        extra_vars = set(variables.keys()) - set(defined_vars)
        if extra_vars:
            raise ValueError(f"Unexpected variables: {extra_vars}")
```

#### 2.3.3 Gateway 实现

**app/core/spec_kit/gateway.py**:

```python
from typing import Dict, Optional
from .prompt_store import PromptStore
from .client import LLMClient
from app.core.outbox import OutboxEventPublisher

class SpecKitGateway:
    """
    Unified AI calling gateway
    - Prompt rendering
    - Model routing
    - Retry/timeout strategies
    - Async logging to ai_calls via Outbox
    """

    def __init__(self):
        self.prompt_store = PromptStore()
        self.llm_client = LLMClient()

    def call(
        self,
        prompt_id: str,
        prompt_version: str,
        variables: Dict,
        model: Optional[str] = None,  # Override model
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
        db_session = None  # For Outbox event writing
    ) -> Dict:
        """
        Execute AI call with prompt rendering and logging

        Returns:
            {
                "result": str | dict,
                "usage": {
                    "input_tokens": int,
                    "output_tokens": int,
                    "cache_read_tokens": int,
                    "cache_write_tokens": int
                },
                "model": str,
                "latency_ms": int
            }
        """
        import time
        start_time = time.time()

        # 1. Render prompt
        rendered = self.prompt_store.render_prompt(
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            variables=variables
        )

        # 2. Determine model (override or default)
        model_to_use = model or rendered['model_default']

        # 3. Call LLM
        try:
            response = self.llm_client.call(
                model=model_to_use,
                prompt=rendered['rendered_text'],
                output_format=rendered['output_format'],
                timeout=60,  # Default timeout
                max_retries=2
            )

            latency_ms = int((time.time() - start_time) * 1000)
            status = "success"
            error_message = None

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            status = self._classify_error(e)
            error_message = str(e)

            # Re-raise exception after logging
            self._log_ai_call(
                db_session=db_session,
                workflow_id=workflow_id,
                task_id=task_id,
                user_id=user_id,
                operation=operation,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                model=model_to_use,
                status=status,
                latency_ms=latency_ms,
                error_message=error_message
            )
            raise

        # 4. Async log to ai_calls via Outbox
        self._log_ai_call(
            db_session=db_session,
            workflow_id=workflow_id,
            task_id=task_id,
            user_id=user_id,
            operation=operation,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model=model_to_use,
            input_tokens=response['usage']['input_tokens'],
            output_tokens=response['usage']['output_tokens'],
            cache_read_tokens=response['usage'].get('cache_read_tokens', 0),
            cache_write_tokens=response['usage'].get('cache_write_tokens', 0),
            estimated_cost=response['usage'].get('cost', 0),
            latency_ms=latency_ms,
            status=status
        )

        return {
            "result": response['result'],
            "usage": response['usage'],
            "model": model_to_use,
            "latency_ms": latency_ms
        }

    def _log_ai_call(self, db_session, **kwargs):
        """Write AI call record to Outbox (async write to ai_calls)"""
        if not db_session:
            return

        OutboxEventPublisher.publish(
            db_session=db_session,
            event_type="ai_call_completed",
            aggregate_type="ai_call",
            aggregate_id=kwargs.get('task_id') or str(uuid.uuid4()),
            payload={
                "workflow_id": kwargs.get('workflow_id'),
                "task_id": kwargs.get('task_id'),
                "operation": kwargs.get('operation'),
                "prompt_id": kwargs.get('prompt_id'),
                "prompt_version": kwargs.get('prompt_version'),
                "model": kwargs.get('model'),
                "input_tokens": kwargs.get('input_tokens', 0),
                "output_tokens": kwargs.get('output_tokens', 0),
                "cache_read_tokens": kwargs.get('cache_read_tokens', 0),
                "cache_write_tokens": kwargs.get('cache_write_tokens', 0),
                "estimated_cost": kwargs.get('estimated_cost', 0),
                "latency_ms": kwargs.get('latency_ms'),
                "status": kwargs.get('status'),
                "error_message": kwargs.get('error_message')
            },
            metadata={
                "user_id": kwargs.get('user_id')
            }
        )

    def _classify_error(self, error: Exception) -> str:
        """Classify error type for logging"""
        error_str = str(error).lower()

        if 'rate limit' in error_str or 'ratelimit' in error_str:
            return 'ratelimit'
        elif 'timeout' in error_str:
            return 'timeout'
        elif 'unauthorized' in error_str or 'invalid_api_key' in error_str:
            return 'auth_error'
        else:
            return 'error'
```

#### 2.3.4 AI Calls 表设计

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

**Outbox Handler for AI Calls** (app/core/outbox/handlers.py):

```python
def log_ai_call(event: OutboxEvent):
    """Write AI call record to ai_calls table"""
    from app.models import AiCall
    from app.database import get_db

    db = next(get_db())

    try:
        ai_call = AiCall(
            user_id=event.metadata.get('user_id'),
            workflow_execution_id=event.payload.get('workflow_id'),
            task_id=event.payload.get('task_id'),
            operation=event.payload.get('operation'),
            prompt_id=event.payload.get('prompt_id'),
            prompt_version=event.payload.get('prompt_version'),
            model=event.payload.get('model'),
            provider=event.payload.get('model', '').split('-')[0],  # Extract provider
            input_tokens=event.payload.get('input_tokens', 0),
            output_tokens=event.payload.get('output_tokens', 0),
            cache_read_tokens=event.payload.get('cache_read_tokens', 0),
            cache_write_tokens=event.payload.get('cache_write_tokens', 0),
            estimated_cost=event.payload.get('estimated_cost', 0),
            latency_ms=event.payload.get('latency_ms'),
            status=event.payload.get('status'),
            error_message=event.payload.get('error_message')
        )

        db.add(ai_call)
        db.commit()

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

# Register handler in OutboxPublisherDaemon
# self.handlers["ai_call_completed"] = log_ai_call
```

### 2.4 任务优先级与配额系统

#### 2.4.1 优先级队列

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

#### 2.4.2 配额管理

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


时间线 T0+26s: Outbox Publisher 处理事件
─────────────────────────────────────────────────────────
  OutboxPublisherDaemon (后台进程，每 5 秒轮询)
    │
    ├─ 查询未发布事件
    │  SELECT * FROM outbox_events
    │  WHERE published = FALSE
    │  ORDER BY created_at
    │  LIMIT 100
    │  FOR UPDATE SKIP LOCKED
    │
    ├─ 处理事件:
    │
    │  ① workflow_completed 事件
    │     → Handler: send_workflow_notification
    │     → Action: WebSocket 推送给用户
    │     → Mark published = TRUE
    │
    │  ② task_completed 事件 (多个)
    │     → Handler: send_task_notification
    │     → Action: WebSocket 更新任务状态
    │     → Mark published = TRUE
    │
    │  ③ ai_call_completed 事件 (3个: detect_language, translate_job, extract_skills)
    │     → Handler: log_ai_call
    │     → Action: 写入 ai_calls 表
    │     → Handler: update_quota
    │     → Action: 扣减用户配额 (仅 success 状态)
    │     → Mark published = TRUE
    │
    └─ COMMIT


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

## 4. 版本管理与切换

### 4.1 版本切换流程

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

### 4.2 Prompt 版本切换 (独立于 config_version)

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

### 4.3 版本回滚

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
