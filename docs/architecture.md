# JobPilot 系统架构设计

## 技术栈

### 前端
- **框架**: React 18 + Vite 5
- **语言**: TypeScript 5.x
- **UI组件**: shadcn/ui + Tailwind CSS + Lucide React
- **状态管理**: Zustand
- **路由**: React Router v6
- **表单**: React Hook Form + Zod + @hookform/resolvers
- **工具库**: clsx, tailwind-merge, class-variance-authority
- **HTTP客户端**: Axios + TanStack Query (React Query)
- **实时通信**: Socket.IO Client
- **Markdown编辑**: React-Markdown-Editor-Lite
- **拖拽**: @hello-pangea/dnd
- **PDF生成**: WeasyPrint (后端)

### 后端
- **框架**: FastAPI 0.109+
- **语言**: Python 3.11+
- **ORM**: SQLAlchemy 2.0 (Async) + Alembic
- **数据库**: PostgreSQL 15+
- **缓存**: Redis 5+ (redis-py)
- **任务队列**: Celery + Redis
- **认证**: python-jose (JWT) + passlib
- **实时通信**: FastAPI WebSocket / python-socketio
- **数据验证**: Pydantic 2.0
- **异步驱动**: asyncpg (PostgreSQL)

### AI Agent
- **SDK**: OpenAI Agents SDK
- **模型**: 简单任务deepseek，复杂任务OpenAI
- **辅助**: deepseek(翻译)

---

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户浏览器                                 │
│                    React + Vite (Port 5173)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Job浏览      │  │ 申请管理      │  │ 简历编辑      │          │
│  │ - 列表/详情  │  │ - Kanban     │  │ - Markdown   │          │
│  │ - 筛选/搜索  │  │ - 时间线     │  │ - 预览       │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────┬────────────────────────────────────────────────────┘
             │ HTTP/REST + WebSocket
             │
┌────────────▼────────────────────────────────────────────────────┐
│               FastAPI Backend Server (Port 8000)                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   中间件层 (Middleware)                     │  │
│  │  - CORS  - JWT认证  - 限流  - 日志  - 异常处理              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Auth API     │  │ Job API      │  │ Application  │        │
│  │ - 注册/登录  │  │ - 查询       │  │ API          │        │
│  │ - JWT验证    │  │ - 分页筛选   │  │ - CRUD       │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Resume API   │  │ AI Agent     │  │ WebSocket    │        │
│  │ - 简历管理   │  │ Service      │  │ 实时通知     │        │
│  │ - 版本控制   │  │ - OpenAI SDK │  │              │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────┬──────────────────┬──────────────────┬───────────────┘
          │                  │                  │
    ┌─────▼─────┐      ┌─────▼─────┐      ┌────▼─────┐
    │PostgreSQL │      │   Redis   │      │  Celery  │
    │  (主库)   │      │  (缓存)   │      │ (队列)   │
    │           │      │           │      │          │
    │ - users   │      │- session  │      │- job分析 │
    │ - jobs    │      │- 匹配缓存 │      │- 简历定制│
    │ - resumes │      │- 配额计数 │      │- 面试准备│
    │ - apps    │      └───────────┘      └────┬─────┘
    └───────────┘                              │
                                               │
                 ┌─────────────────────────────▼──────────┐
                 │         Celery Workers (Python)         │
                 │  ┌──────────────┐  ┌──────────────┐   │
                 │  │ Job Analysis │  │ Application  │   │
                 │  │ Task         │  │ Task         │   │
                 │  └──────────────┘  └──────────────┘   │
                 │  ┌──────────────┐  ┌──────────────┐   │
                 │  │ Interview    │  │ Match Score  │   │
                 │  │ Prep Task    │  │ Task         │   │
                 │  └──────────────┘  └──────────────┘   │
                 └────────────┬────────────────────────────┘
                              │
                     ┌────────▼──────────┐
                     │  AI Models APIs   │
                     │ ┌───────────────┐ │
                     │ │ DeepSeek      │ │
                     │ │ - 翻译        │ │
                     │ │ - 简单任务    │ │
                     │ └───────────────┘ │
                     │ ┌───────────────┐ │
                     │ │ OpenAI        │ │
                     │ │ - 复杂任务    │ │
                     │ │ - Agent工作流 │ │
                     │ └───────────────┘ │
                     └───────────────────┘
```

---

## 项目结构

### 前端 (React + Vite)

```
frontend/
├── public/
├── src/
│   ├── api/                    # API调用封装
│   │   ├── jobs.ts
│   │   ├── applications.ts
│   │   ├── resumes.ts
│   │   └── auth.ts
│   ├── components/             # 通用组件
│   │   ├── ui/                 # shadcn/ui组件
│   │   ├── JobCard/
│   │   ├── ApplicationCard/
│   │   ├── MarkdownEditor/
│   │   └── KanbanBoard/
│   ├── features/               # 功能模块
│   │   ├── jobs/
│   │   │   ├── JobList.tsx
│   │   │   ├── JobDetail.tsx
│   │   │   └── JobFilters.tsx
│   │   ├── applications/
│   │   │   ├── ApplicationList.tsx
│   │   │   ├── ApplicationDetail.tsx
│   │   │   ├── KanbanView.tsx
│   │   │   └── Timeline.tsx
│   │   ├── resumes/
│   │   │   ├── ResumeList.tsx
│   │   │   ├── ResumeEditor.tsx
│   │   │   └── ResumePreview.tsx
│   │   └── auth/
│   │       ├── Login.tsx
│   │       └── Register.tsx
│   ├── hooks/                  # 自定义Hooks
│   │   ├── useJobs.ts
│   │   ├── useApplications.ts
│   │   ├── useResumes.ts
│   │   └── useWebSocket.ts
│   ├── store/                  # Zustand状态管理
│   │   ├── authStore.ts
│   │   ├── jobStore.ts
│   │   └── uiStore.ts
│   ├── types/                  # TypeScript类型
│   │   ├── job.ts
│   │   ├── application.ts
│   │   └── resume.ts
│   ├── utils/                  # 工具函数
│   │   ├── formatters.ts
│   │   └── validators.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── router.tsx
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

### 后端 (FastAPI + Python)

```
backend/
├── .venv/                            # python虚拟环境目录
├── alembic/                          # 数据库迁移
│   ├── versions/                     # 迁移版本文件
│   └── env.py                        # Alembic 配置
├── app/
│   ├── core/                         # 核心配置 (全局共享)
│   │   ├── __init__.py
│   │   ├── config.py                 # 应用配置 (Settings)
│   │   ├── database.py               # 数据库连接池
│   │   ├── security.py               # JWT/密码工具
│   │   ├── exceptions.py             # 自定义异常
│   │   └── celery_app.py             # Celery 配置
│   │
│   ├── modules/                      # 业务模块 (按功能领域划分)
│   │   │
│   │   ├── auth/                     # 认证模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # 认证 API 路由
│   │   │   ├── service.py            # 认证业务逻辑
│   │   │   ├── models.py             # User 模型
│   │   │   ├── schemas.py            # 登录/注册请求响应模式
│   │   │   ├── dependencies.py       # JWT验证、权限检查依赖
│   │   │   └── utils.py              # Token生成、密码哈希
│   │   │
│   │   ├── jobs/                     # Job 模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # Job API 路由
│   │   │   ├── service.py            # Job 业务逻辑
│   │   │   ├── models.py             # SeekJob 模型 (只读访问)
│   │   │   └── schemas.py            # Job 请求/响应模式
│   │   │
│   │   ├── applications/             # 申请模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # 申请 API 路由
│   │   │   ├── service.py            # 申请业务逻辑
│   │   │   ├── models.py             # Application/TimelineEvent 模型
│   │   │   ├── schemas.py            # 申请请求/响应模式
│   │   │   ├── tasks.py              # 申请材料生成任务
│   │   │   └── enums.py              # ApplicationStatus 枚举
│   │   │
│   │   ├── resumes/                  # 简历模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # 简历 API 路由
│   │   │   ├── service.py            # 简历业务逻辑
│   │   │   ├── models.py             # Resume/Document 模型
│   │   │   ├── schemas.py            # 简历请求/响应模式
│   │   │   └── export/               # 文档导出子模块
│   │   │       ├── __init__.py
│   │   │       ├── service.py        # DocumentExportService (通用导出)
│   │   │       ├── generator.py      # PDFGenerator (WeasyPrint)
│   │   │       ├── renderer.py       # HTMLRenderer (模板渲染)
│   │   │       ├── templates/        # HTML 模板 (按文档类型分类)
│   │   │       │   ├── resume/       # 简历模板 (modern/classic/minimal)
│   │   │       │   └── cover_letter/ # 求职信模板
│   │   │       ├── css/              # 样式文件 (按文档类型分类)
│   │   │       │   ├── resume/       # 简历样式
│   │   │       │   └── cover_letter/ # 求职信样式
│   │   │       └── static/           # 静态资源 (字体等)
│   │   │
│   │   ├── users/                    # 用户模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # 用户 API 路由
│   │   │   ├── service.py            # 用户业务逻辑
│   │   │   ├── models.py             # UserSkill 模型
│   │   │   └── schemas.py            # 用户请求/响应模式
│   │   │
│   │   ├── ai_agent/                 # AI Agent 模块
│   │   │   ├── __init__.py
│   │   │   ├── service.py            # AI Agent 统一服务
│   │   │   ├── agents/               # 各类 Agent 实现
│   │   │   │   ├── __init__.py
│   │   │   │   ├── job_analysis.py   # Job 分析 Agent
│   │   │   │   ├── resume_tailor.py  # 简历定制 Agent
│   │   │   │   ├── cover_letter.py   # 求职信生成 Agent
│   │   │   │   └── interview_prep.py # 面试准备 Agent
│   │   │   ├── tools/                # Agent 工具函数
│   │   │   │   ├── __init__.py
│   │   │   │   ├── skill_extractor.py# 技能提取 (spaCy)
│   │   │   │   ├── translator.py     # 翻译工具 (DeepSeek)
│   │   │   │   └── quality_check.py  # 质量检查
│   │   │   ├── prompts/              # Agent 提示词模板
│   │   │   │   ├── __init__.py
│   │   │   │   ├── job_analysis.py
│   │   │   │   ├── resume_tailor.py
│   │   │   │   └── cover_letter.py
│   │   │   ├── models.py             # AiUsage 模型
│   │   │   └── schemas.py
│   │   │
│   │   └── websocket/                # WebSocket 模块
│   │       ├── __init__.py
│   │       ├── router.py             # WebSocket 端点
│   │       ├── manager.py            # 连接管理器
│   │       └── events.py             # 事件处理
│   │
│   ├── shared/                       # 共享模块 (跨模块复用)
│   │   ├── __init__.py
│   │   ├── base_model.py             # SQLAlchemy 基类模型
│   │   ├── base_schema.py            # Pydantic 基类模式
│   │   ├── pagination.py             # 分页工具
│   │   ├── enums.py                  # 全局枚举 (Role等)
│   │   └── utils.py                  # 通用工具函数
│   │
│   ├── api/                          # API 路由聚合层
│   │   ├── __init__.py
│   │   ├── deps.py                   # 全局依赖注入 (get_db等)
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py             # 聚合所有模块路由
│   │
│   └── main.py                       # FastAPI 应用入口
│
├── tests/                            # 测试 (镜像 app 结构)
│   ├── __init__.py
│   ├── conftest.py                   # Pytest 配置
│   ├── unit/                         # 单元测试
│   │   ├── test_auth.py
│   │   ├── test_jobs.py
│   │   └── test_applications.py
│   └── integration/                  # 集成测试
│       └── test_api.py
│
├── scripts/                          # 工具脚本
│   ├── init_db.py                    # 初始化数据库
│   ├── seed_data.py                  # 种子数据
│   └── celery_worker.py              # Celery worker 启动
│
├── pyproject.toml                    # uv 依赖管理
├── alembic.ini                       # Alembic 配置
├── .env.example                      # 环境变量示例
└── README.md
```

---

## 核心模块设计

### 1. Auth Module (认证授权)

**功能覆盖**：
- 用户注册/登录
- JWT Token 管理
- 角色权限控制 (USER/VIP/ADMIN)
- 配额验证和追踪

**核心机制**：
- 使用 JWT 进行无状态认证
- 基于角色的访问控制 (RBAC)
- 月度配额检查 (拦截器模式)

---

### 2. Job Module (职位管理)

**功能覆盖**：
- Job 列表查询 (只读)
- 服务器端分页 (每页 20 条)
- 多维度筛选 (地点/类型/公司/时间)
- PostgreSQL 全文搜索
- 匹配度/紧急度展示
- 相似职位推荐

**数据来源**：
- 外部爬虫系统维护 `seek_jobs` 表
- JobPilot 只读访问
- 通过 `JobAnalysis` 表存储 AI 分析结果

**查询流程**：
```
用户请求 → 应用过滤条件 → 联表查询 JobMatch (获取匹配度) → 分页返回
```

---

### 3. Application Module (申请管理)

**功能覆盖**：
- 申请 CRUD 操作
- 状态流转管理
- 时间线记录
- 批量操作 (批量标记状态)
- 申请材料版本化
- 软删除和恢复

**状态流转**：
```
Pending → Tailoring → Ready → Applied → ResumeScreened → PhoneScreen → Interviewing → Offer/Rejected
         ↓                                                                    ↓
       (AI生成中)                                                        (触发面试准备)
```

**核心操作流程**：

**创建申请**：
```
1. 检查唯一性 (user_id + job_id)
2. 创建 Application 记录 (status: Pending)
3. 记录时间线事件 (created)
4. 触发工作流 (入队 Celery)
```

**状态更新**：
```
1. 更新 Application.status
2. 记录时间线事件 (status_changed)
3. 触发后续动作 (如 Interviewing → 生成面试准备材料)
```

---

### 4. Resume Module (简历管理)

**功能覆盖**：
- 简历模板管理 (CRUD)
- 草稿/正式版本控制
- 软删除和恢复
- 简历内容版本历史
- 与申请关联追踪

**业务规则**：
- **正式简历数量限制**: 由全局配置 `FORMAL_RESUME_LIMIT` 控制（非用户级字段）
  * 默认值：所有角色统一限制（如 5 个）
  * 可在系统配置文件或环境变量中调整
  * 超过限制时，无法创建新的正式简历

**数据模型设计**：

**两层结构**：
```
Resume (简历元数据：title, isDraft, 软删除标记)
  └── Document (文档内容 + 版本链)
```

**Document 链式版本模型**：
- 所有版本存储在同一张 `document` 表
- `rootId`: 文档家族根ID（第一版自引用）
- `parentId`: 内容来源（跨家族指向模板，同家族指向上一版本）
- `format`: 文档格式（Markdown / HTML / PlainText）
- `contentHash`: 内容哈希（幂等判断和缓存）
- `metadata`: JSON 扩展字段（业务自定义，可存储文档类型等业务信息）

**定制简历生成流程**：
```
1. 读取简历模板 (Resume → Document)
2. AI 定制内容
3. 创建新 Document (parentId: 模板Document.id, rootId: 生成新的family)
4. 关联到 Application.resumeDocumentId
```

**版本管理策略**：
- 用户手动编辑 → 创建新 Document (parentId: 上一版本ID, rootId: 保持不变)
- AI 重新生成 → 创建新 Document (parentId: 模板ID, rootId: **保持不变**，属于同一文档家族)
  * 说明：对同一申请的简历/求职信重新生成时，使用相同的 rootId，表示它们属于同一文档家族
  * 不同申请即使使用同一模板，也会创建不同的 rootId (不同家族)
- 保留 `changeComments` 字段记录修改原因

---

### 5. AI Agent Module (核心 AI 能力)

**功能覆盖**：
- Job 分析 (HTML→Markdown、翻译、技能提取)
- 简历定制 (Deep/Light 两种策略)
- Cover Letter 生成
- 质量检查
- 面试准备材料生成
- 简历推荐

**模型选择策略**：
- **DeepSeek**: 翻译、简单文本处理
- **OpenAI GPT-4**: 复杂任务 (简历定制、求职信生成、面试准备)

**Agent 工作流模式**：
```
1. 接收任务参数
2. 调用 AI 模型 (OpenAI Agents SDK)
3. 可选工具调用 (skill_extractor, translator, quality_check)
4. 保存结果到数据库
5. 记录 token 使用量 (AiUsage 表)
```

**核心任务类型**：
1. **job_analysis**: 分析职位描述，提取技能要求、经验要求等
2. **tailor_resume**: 根据职位要求定制简历（Deep/Light两种深度）
3. **generate_cover_letter**: 生成求职信
4. **quality_check**: 质量检查定制后的简历和求职信
5. **resume_recommendation**: 简历推荐
   - 输入：用户所有简历 + 职位要求
   - 输出：最佳匹配简历ID + 匹配详情
   - 结果存储：`JobMatch.bestMatchedResumeId` 和 `JobMatch.matchDetails`
   - 触发时机：Job 分析完成后，由工作流自动触发

**配额管理**：
- 按用户追踪 AI 使用量 (输入/输出 tokens)
- 预估成本计算
- 按操作类型分类统计

**配额管理时机**：
1. **检查时机** (API Layer)：
   - 用户发起 AI 相关请求时（创建 Application、Job Analysis 等）
   - 在工作流启动前检查配额是否充足
   - 如配额不足，直接拒绝请求并返回错误

2. **扣除时机** (Outbox Layer)：
   - AI 任务成功完成后，在 Outbox Pattern 事件发布时扣除
   - 基于实际使用的 tokens 进行扣除
   - 如任务失败，不扣除配额
   - 通过 `AiUsage` 表记录每次使用详情

3. **配额重置**：
   - 由定时任务（Celery Beat）每月重置配额
   - 更新 `User.monthlyTokenLeft` 和 `User.quotaResetAt`

---

### 6. Workflow Module (工作流管理)

**功能覆盖**：
- 工作流定义和执行
- 任务依赖管理 (串行/并行)
- 状态持久化和恢复
- 失败重试机制
- 版本管理
- 执行历史追踪

**架构分层**：
```
API Layer (FastAPI)
  ↓ 创建工作流
Orchestration Layer (Workflow Service)
  ↓ 构建 DAG
Execution Layer (Celery Workers)
  ↓ 执行任务
Storage Layer (PostgreSQL + Redis)
```

**核心工作流类型**：

**1. Job Analysis Workflow**：
```
fetch_html → html_to_markdown → translate_job → extract_skills → 更新 Job 表
```

**2. Application Generation Workflow** (并行执行)：
```
                ┌─ tailor_resume ─┐
开始 ─┤                          ├─ quality_check → 完成
                └─ generate_cover_letter ─┘
```

**工作流状态**：
- `pending`: 等待执行
- `running`: 执行中
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

**任务状态**：
- `pending`: 等待执行
- `running`: 执行中
- `success`: 成功
- `failed`: 失败
- `retry`: 重试中

**执行流程**：
```
1. API 接收请求
2. 创建 WorkflowExecution 记录 (status: pending)
3. 创建所有 TaskExecution 记录 (预占位)
4. 加载工作流配置 (从 YAML)
5. 构建 Celery Canvas (chain/chord)
6. 提交执行 (apply_async)
7. Worker 逐步执行任务，更新状态
8. WebSocket 推送进度通知
9. 完成后更新 WorkflowExecution (status: completed)
```

**版本管理方案**：

**目录结构**：
```
workflows/
├── job_analysis/
│   ├── v1.0.0.yaml
│   ├── v1.1.0.yaml
│   └── v2.0.0.yaml
├── application_generation/
│   ├── v1.0.0.yaml
│   └── v1.1.0.yaml
└── registry.yaml  # 版本注册表 (记录 active_version)
```

**版本切换**：
```
1. 编辑 registry.yaml (修改 active_version)
2. 重启 Worker 或调用热更新 API
3. 新创建的工作流自动使用新版本
4. 数据库记录每次执行的 config_version
```

**异常处理**：

**任务级重试** (Celery 原生)：
- 指数退避策略 (60s, 120s, 240s)
- 可配置最大重试次数
- 区分可重试错误 (RateLimitError) 和不可重试错误 (InvalidAPIKey)

**僵尸任务清理**：
- 定时任务扫描 (每 5 分钟)
- 检测超时未更新的 `running` 任务
- 对比 PostgreSQL 和 Celery 状态
- 自动标记失败并告警

**定时任务协调**：

系统使用 **Celery Beat** 作为定时任务调度器，负责触发周期性工作流：

```python
# celery_beat_schedule 配置示例
{
    'quota-reset-monthly': {
        'task': 'tasks.quota.reset_monthly_quota',
        'schedule': crontab(day_of_month='1', hour='0', minute='0'),
    },
    'zombie-task-cleanup': {
        'task': 'tasks.workflow.cleanup_zombie_tasks',
        'schedule': crontab(minute='*/5'),  # 每5分钟
    },
}
```

**工作流触发方式**：
1. **用户操作触发**: API 接收请求后直接创建工作流（如创建 Application）
2. **定时任务触发**: Celery Beat 按时间表触发（如配额重置、僵尸任务清理）
3. **事件驱动触发**: 通过 Outbox Pattern 发布的事件触发后续工作流（如 Job 分析完成后触发简历推荐）

**注意事项**：
- 批量操作（如批量导入 Job）**不会自动触发工作流**，需要用户显式触发分析
- 定时任务失败会记录到 `TaskExecution` 表，并通过告警系统通知管理员

---

### 7. WebSocket Gateway (实时通信)

**功能覆盖**：
- 任务进度实时推送
- 申请状态变更通知
- 配额预警
- 房间管理 (按 application_id 分组)

**通信模式**：
```
客户端 → join-application(applicationId) → 加入房间
Worker → 更新状态 → WebSocket Gateway → emit('progress', data) → 客户端
```

**消息类型**：
- `progress`: 任务进度更新 (百分比、当前阶段)
- `status-change`: 状态变更通知
- `quota-warning`: 配额预警
- `error`: 错误通知

**消息格式示例**：

```json
// progress - 任务进度更新
{
  "type": "progress",
  "applicationId": "app_123",
  "workflowId": "wf_456",
  "taskName": "tailor_resume",
  "progress": 65,
  "message": "正在定制简历..."
}

// status-change - 状态变更
{
  "type": "status-change",
  "applicationId": "app_123",
  "oldStatus": "Pending",
  "newStatus": "Ready",
  "timestamp": "2025-01-15T10:30:00Z"
}

// quota-warning - 配额预警
{
  "type": "quota-warning",
  "userId": "user_123",
  "quotaType": "monthlyToken",
  "remaining": 5000,
  "limit": 100000,
  "message": "Token配额即将用尽（剩余5%）"
}

// error - 错误通知
{
  "type": "error",
  "applicationId": "app_123",
  "taskName": "generate_cover_letter",
  "error": "API rate limit exceeded",
  "retryable": true
}
```

---

## 模块间协作流程

### 完整申请流程示例

```
1. 用户在 Job 详情页点击"申请"
   ↓
2. Application Module 创建申请 (status: Pending)
   ↓
3. Workflow Module 启动 application_generation 工作流
   ↓
4. AI Agent Module 并行执行：
   - 简历定制 (基于用户选择的 Resume)
   - 求职信生成
   ↓
5. Resume Module 创建定制文档：
   - 创建 Document (parentId: 模板Document.id, rootId: 自身id)
   - 创建 Document (parentId: null, rootId: 自身id)
   ↓
6. AI Agent Module 质量检查
   ↓
7. Application Module 更新状态 (status: Ready)
   - 关联定制文档 (resumeDocumentId, coverLetterDocumentId)
   - 记录时间线事件
   ↓
8. WebSocket Gateway 推送完成通知
   ↓
9. 前端跳转到申请详情页，展示定制材料
```

---

## 核心设计模式

**1. Document 链式版本模式**：
```
所有文档内容 (简历/求职信) 统一存储在 Document 表
- 链式版本：rootId 聚合文档家族，parentId 追溯内容来源
- 内容哈希去重：contentHash 支持幂等判断和缓存
- 跨家族派生：定制简历的 parentId 指向模板，表示内容来源
- 业务元数据分离：metadata JSON 字段由业务层自定义
```

**2. 软删除模式**：
```
关键业务实体 (Application, Resume) 采用软删除
- isDeleted + deletedAt 字段
- 支持恢复操作
- 保留历史数据用于审计
- Document 表不处理软删除，由业务层管理
```

**3. 时间线记录模式**：
```
Application 关联 TimelineEvent[]
- 记录所有状态变更
- 记录用户备注
- 支持审计追踪
```

**4. 配置驱动工作流**：
```
工作流定义存储在 YAML 文件
- 代码与配置分离
- 支持版本管理
- 无需重新部署即可修改流程
```

---

## 数据库Schema

// ============================================
// 枚举类型
// ============================================

enum Role {
  USER
  VIP
  ADMIN
}

enum ApplicationStatus {
  Pending         // 待处理
  Tailoring       // AI定制中
  Ready           // 材料已就绪
  Applied         // 已申请
  ResumeScreened  // 简历筛查通过
  PhoneScreen     // 电话沟通
  Interviewing    // 面试中
  Offer           // 获得Offer
  Rejected        // 被拒绝
}

enum ProficiencyLevel {
  Beginner
  Intermediate
  Advanced
  Expert
}

enum DocumentFormat {
  Markdown
  HTML
  PlainText
}

### users
```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role role NOT NULL DEFAULT 'USER',
  preferences JSONB,
  linkedin_connected BOOLEAN NOT NULL DEFAULT FALSE,
  monthly_job_limit INTEGER NOT NULL DEFAULT 0,
  monthly_token_limit INTEGER NOT NULL DEFAULT 0,
  monthly_token_left INTEGER NOT NULL DEFAULT 0,
  quota_reset_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### documents (��ʽ�汾ģ��)
```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  root_id TEXT NOT NULL,
  parent_id TEXT,
  format document_format NOT NULL DEFAULT 'Markdown',
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  change_comments TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by TEXT NOT NULL,
  CONSTRAINT fk_documents_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_documents_parent FOREIGN KEY (parent_id) REFERENCES documents(id) ON DELETE SET NULL
);

CREATE INDEX idx_documents_root_created_at_desc ON documents (root_id, created_at DESC);
CREATE INDEX idx_documents_parent_id ON documents (parent_id);
CREATE INDEX idx_documents_created_by ON documents (created_by);
CREATE INDEX idx_documents_content_hash ON documents (content_hash);
```

### resumes
```sql
CREATE TABLE resumes (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  document_id TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  is_draft BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  CONSTRAINT fk_resumes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_resumes_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  CONSTRAINT uq_resumes_user_title UNIQUE (user_id, title)
);

CREATE INDEX idx_resumes_user_draft_deleted ON resumes (user_id, is_draft, is_deleted);
CREATE INDEX idx_resumes_user_deleted ON resumes (user_id, is_deleted);
```

### seek_jobs (ֻ����Դ��)
```sql
CREATE TABLE seek_jobs (
  id BIGSERIAL PRIMARY KEY,
  source_id TEXT NOT NULL UNIQUE,
  title VARCHAR(500) NOT NULL,
  abstract TEXT,
  content TEXT,
  status VARCHAR(50),
  is_expired BOOLEAN DEFAULT FALSE,
  is_link_out BOOLEAN DEFAULT FALSE,
  is_verified BOOLEAN DEFAULT FALSE,
  phone_number VARCHAR(50),
  share_link TEXT,
  listed_at TIMESTAMPTZ(6),
  expires_at TIMESTAMPTZ(6),
  salary_label VARCHAR(200),
  work_types_label VARCHAR(100),
  work_type_ids VARCHAR(50),
  location_label VARCHAR(200),
  location_area VARCHAR(100),
  location_city VARCHAR(100),
  location_ids TEXT,
  country_code VARCHAR(10),
  country VARCHAR(50),
  suburb VARCHAR(100),
  region VARCHAR(100),
  state VARCHAR(100),
  postcode VARCHAR(20),
  advertiser_id VARCHAR(50),
  advertiser_name VARCHAR(300),
  advertiser_is_verified BOOLEAN DEFAULT FALSE,
  advertiser_registration_date TIMESTAMPTZ(6),
  is_private_advertiser BOOLEAN DEFAULT FALSE,
  classification_id VARCHAR(20),
  classification VARCHAR(200),
  sub_classification_id VARCHAR(20),
  sub_classification VARCHAR(200),
  classifications_label VARCHAR(500),
  product_bullets TEXT,
  branding_id VARCHAR(100),
  branding_cover_url TEXT,
  branding_thumbnail_url TEXT,
  branding_logo_url TEXT,
  display_tags TEXT,
  company_profile_id VARCHAR(50),
  company_name VARCHAR(300),
  company_slug VARCHAR(200),
  company_logo TEXT,
  company_description TEXT,
  company_industry VARCHAR(100),
  company_size VARCHAR(100),
  company_website TEXT,
  should_display_reviews BOOLEAN DEFAULT FALSE,
  normalised_role_title VARCHAR(300),
  normalised_organisation_name VARCHAR(300),
  broader_location_name VARCHAR(100),
  source_zone VARCHAR(20),
  ad_product_type VARCHAR(50),
  has_role_requirements BOOLEAN DEFAULT FALSE,
  contact_phone VARCHAR(50),
  contact_email VARCHAR(100),
  restricted_application_label VARCHAR(200),
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ(6) NOT NULL DEFAULT now()
);

CREATE INDEX idx_seek_jobs_source_id ON seek_jobs (source_id);
CREATE INDEX idx_seek_jobs_title ON seek_jobs (title);
CREATE INDEX idx_seek_jobs_listed_at ON seek_jobs (listed_at);
CREATE INDEX idx_seek_jobs_is_expired ON seek_jobs (is_expired);
CREATE INDEX idx_seek_jobs_status ON seek_jobs (status);
CREATE INDEX idx_seek_jobs_location_city ON seek_jobs (location_city);
CREATE INDEX idx_seek_jobs_advertiser_name ON seek_jobs (advertiser_name);
CREATE INDEX idx_seek_jobs_classification ON seek_jobs (classification);
CREATE INDEX idx_seek_jobs_sub_classification ON seek_jobs (sub_classification);
```

### job_analysis
```sql
CREATE TABLE job_analysis (
  id TEXT PRIMARY KEY,
  job_id BIGINT NOT NULL UNIQUE,
  required_skills TEXT[] NOT NULL DEFAULT '{}',
  optional_skills TEXT[] NOT NULL DEFAULT '{}',
  soft_skills TEXT[] NOT NULL DEFAULT '{}',
  years_experience INTEGER,
  deadline TIMESTAMPTZ,
  markdown_content TEXT,
  translated_content TEXT,
  original_language VARCHAR(10),
  analysis_result VARCHAR(50),
  error_message TEXT,
  analyzed_at TIMESTAMPTZ,
  CONSTRAINT fk_job_analysis_job FOREIGN KEY (job_id) REFERENCES seek_jobs(id) ON DELETE CASCADE
);
```

### job_matches
```sql
CREATE TABLE job_matches (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  job_id BIGINT NOT NULL,
  match_score NUMERIC(5,2) NOT NULL,
  urgency_score NUMERIC(5,2),
  best_matched_resume_id TEXT,
  match_details JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_job_matches_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_job_matches_job FOREIGN KEY (job_id) REFERENCES seek_jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_job_matches_best_resume FOREIGN KEY (best_matched_resume_id) REFERENCES resumes(id),
  CONSTRAINT uq_job_matches_user_job UNIQUE (user_id, job_id)
);

CREATE INDEX idx_job_matches_user_match_score_desc ON job_matches (user_id, match_score DESC);
CREATE INDEX idx_job_matches_user_urgency_score_desc ON job_matches (user_id, urgency_score DESC);
```

### applications
```sql
CREATE TABLE applications (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  job_id BIGINT NOT NULL,
  source_resume_id TEXT NOT NULL,
  tailoring_level TEXT,
  status application_status NOT NULL DEFAULT 'Pending',
  resume_document_id TEXT,
  cover_letter_document_id TEXT,
  resume_verified BOOLEAN NOT NULL DEFAULT FALSE,
  cover_letter_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  CONSTRAINT fk_applications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_applications_job FOREIGN KEY (job_id) REFERENCES seek_jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_applications_source_resume FOREIGN KEY (source_resume_id) REFERENCES resumes(id),
  CONSTRAINT fk_applications_resume_doc FOREIGN KEY (resume_document_id) REFERENCES documents(id) ON DELETE SET NULL,
  CONSTRAINT fk_applications_cover_letter_doc FOREIGN KEY (cover_letter_document_id) REFERENCES documents(id) ON DELETE SET NULL,
  CONSTRAINT uq_applications_user_job UNIQUE (user_id, job_id)
);

CREATE INDEX idx_applications_user_updated_desc ON applications (user_id, updated_at DESC);
CREATE INDEX idx_applications_user_status_deleted ON applications (user_id, status, is_deleted);
CREATE INDEX idx_applications_user_deleted ON applications (user_id, is_deleted);
CREATE INDEX idx_applications_status ON applications (status);
CREATE INDEX idx_applications_resume_document_id ON applications (resume_document_id);
CREATE INDEX idx_applications_cover_letter_document_id ON applications (cover_letter_document_id);
```

### timeline_events
```sql
CREATE TABLE timeline_events (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL,
  event TEXT NOT NULL,
  note TEXT,
  metadata JSONB,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_timeline_events_application FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE INDEX idx_timeline_events_application_timestamp_desc ON timeline_events (application_id, timestamp DESC);
```

### user_skills
```sql
CREATE TABLE user_skills (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  skill_name TEXT NOT NULL,
  proficiency proficiency_level NOT NULL,
  skill_type TEXT NOT NULL,
  extracted_from_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_user_skills_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT uq_user_skills_user_skill UNIQUE (user_id, skill_name)
);

CREATE INDEX idx_user_skills_user_skill_type ON user_skills (user_id, skill_type);
```

### ai_usage
```sql
CREATE TABLE ai_usage (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  cache_write_tokens INTEGER NOT NULL DEFAULT 0,
  estimated_cost NUMERIC(10,6) NOT NULL,
  operation TEXT NOT NULL,
  object_id TEXT,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_ai_usage_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_ai_usage_user_timestamp ON ai_usage (user_id, timestamp);
CREATE INDEX idx_ai_usage_user_operation ON ai_usage (user_id, operation);
```


---

## 未来扩展功能

### Interview Preparation (面试准备)

**功能概述**: 基于职位要求和用户简历，自动生成面试准备材料，包括常见问题预测、STAR 方法答案建议、技术问题准备等。

**实现要点**:
- 新增 `InterviewPrep` 表存储面试准备材料
- AI 任务类型：`interview_prep_generation`
- 触发时机：Application 状态变为 Ready 后，用户手动触发
- 输出内容：常见问题列表、建议回答、技术准备要点

### Company Research (公司调研)

**功能概述**: 自动收集和分析目标公司信息，帮助用户了解公司文化、产品、近期新闻等，为面试做准备。

**实现要点**:
- 新增 `CompanyResearch` 表存储调研结果
- 集成外部数据源（公司官网、LinkedIn、新闻API等）
- AI 任务类型：`company_research`
- 触发时机：用户在 Application 详情页手动触发
- 输出内容：公司概况、文化特点、产品分析、近期动态

---
