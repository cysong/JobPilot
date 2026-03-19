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
│   │   ├── api.ts              # 统一API响应类型
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
│   │   ├── celery_app.py             # Celery 配置
│   │   ├── response_codes.py         # 响应码定义
│   │   ├── response.py               # 统一响应模型
│   │   └── custom_route.py           # 自定义路由类
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
│   │   ├── workflow/                 # 工作流模块
│   │   │   ├── __init__.py
│   │   │   ├── base_task.py          # Celery Task 基类
│   │   │   │                         # - AsyncBaseTask (异步+DB)
│   │   │   │                         # - DBTrackingTask (追踪)
│   │   │   ├── task_service.py       # 任务服务 (提交/查询)
│   │   │   ├── models.py             # TaskExecution 模型
│   │   │   ├── schemas.py            # 任务请求/响应模式
│   │   │   ├── repositories.py       # TaskRepository
│   │   │   └── enums.py              # TaskStatus/TaskType 枚举
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

**结构化输出容错策略**：
- `openai` provider 和纯文本输出保持 SDK 原生 `output_type` 行为，不增加额外清洗。
- 非 `openai` provider 的结构化输出使用 `CleaningOutputSchema`，在 `validate_json()` 前做轻量格式清洗后再交给 SDK 原始 schema 校验。
- 轻量清洗仅包含：原文直验、去掉整段 fenced JSON、提取 fenced block 内 JSON、提取首个平衡 JSON 对象/数组；不做字段修复、自动补全或重试调用。
- 记录结构化输出校验日志，区分原始直接通过、清洗后恢复通过、清洗后仍失败，用于统计第三方模型结构化输出稳定性。

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

### 6. Task Execution Module (任务执行系统)

**设计理念**：
- **极简化数据库**：单表设计（task_executions），workflow 作为逻辑概念
- **双层基类架构**：AsyncBaseTask（异步+DB）+ DBTrackingTask（追踪）
- **零样板代码**：自动会话管理、自动状态追踪
- **渐进式增强**：简单任务用 AsyncBaseTask，复杂任务用 DBTrackingTask

**核心目标**：
- ✅ 消除异步包装器和装饰器
- ✅ 自动注入 `self.db` 数据库会话
- ✅ 自动追踪任务状态（PENDING → RUNNING → SUCCESS/FAILED）
- ✅ 简化数据模型（从2张表降至1张表）

---

#### 6.1 Celery Task 基类架构

**双层基类设计**：

```
celery.Task
    ↓
AsyncBaseTask (第一层)
  • 自动检测 async 函数
  • 自动创建并注入 db session
  • 提供 self.db 属性
  • 自动会话生命周期管理
  • 错误时自动回滚
    ↓
DBTrackingTask (第二层)
  • 继承 AsyncBaseTask 所有能力
  • 任务状态自动追踪
  • 生命周期钩子 (before_start, on_success, on_failure)
  • 执行时间记录
```

**任务类型选择**：

| 任务类型 | 基类 | 使用场景 |
|---------|------|---------|
| 追踪任务 | `DBTrackingTask` | Job分析、简历定制、求职信生成 |
| 批处理/定时任务 | `AsyncBaseTask` | 批量匹配、定时清理 |
| 简单任务 | 无基类 | 纯计算、外部API调用 |

**使用示例**：

```python
# 批处理任务：使用 AsyncBaseTask
@celery_app.task(base=AsyncBaseTask, bind=True)
async def batch_processing(self, params):
    results = await process_batch(self.db, params)
    await self.db.commit()
    return results

# 追踪任务：使用 DBTrackingTask
@celery_app.task(base=DBTrackingTask, bind=True)
async def analyze_job(self, job_id: int):
    job = await JobRepository.get_by_id(self.db, job_id)
    result = await process(self.db, job_id)
    await self.db.commit()
    return {"output_data": {...}}
```

---

#### 6.2 数据库设计（极简单表）

**核心理念**：
- 去掉 `workflow_executions` 表
- `workflow_id` 只是逻辑分组ID，多个task共享表示同一批次
- `task` 是唯一执行单元，独立追踪状态

**task_executions 表核心字段**：
- `workflow_id`: 逻辑分组ID（非外键）
- `entity_type` + `entity_id`: 业务实体关联
- `user_id`: 用户ID
- `task_type` + `task_name`: 任务类型和名称
- `status`: 任务状态（PENDING/RUNNING/SUCCESS/FAILED）
- `input_data` + `output_data`: 任务输入输出（JSON）
- `celery_task_id`: Celery任务ID
- `execution_time_ms`: 执行耗时

**使用模式**：

**单任务**（最常见）：
```python
# workflow_id = task_id (单任务场景)
await TaskService.submit_task(
    db,
    task_type=TaskType.JOB_ANALYSIS,
    entity_type="job",
    entity_id="123",
    user_id=1,
    job_id=123  # 传给 Celery
)
```

**多任务批次**：
```python
workflow_id = str(uuid4())  # 共享批次ID

# Task 1: 分析简历
await TaskService.submit_task(
    db, workflow_id=workflow_id,
    task_type=TaskType.RESUME_ANALYSIS,
    entity_type="resume", entity_id=resume_id
)

# Task 2: 匹配工作（使用 Celery chain 串行执行）
await TaskService.submit_task(
    db, workflow_id=workflow_id,
    task_type=TaskType.MATCH_JOBS,
    entity_type="resume", entity_id=resume_id
)
```

**任务状态**：
- `PENDING`: 等待执行
- `RUNNING`: 执行中
- `SUCCESS`: 成功
- `FAILED`: 失败

---

#### 6.3 任务执行流程

**简化的执行流程**：
```
1. API 接收请求
2. TaskService.submit_task()
   - 创建 TaskExecution 记录 (status: PENDING)
   - 提交到 Celery
3. Worker 执行任务
   - before_start 钩子：更新为 RUNNING
   - 执行 task.run()
   - on_success 钩子：更新为 SUCCESS，保存 output_data
   - on_failure 钩子：更新为 FAILED，记录错误
4. WebSocket 推送进度通知
```

**对比旧流程**（已废弃）：
- ❌ 旧流程：创建 WorkflowExecution → 创建 TaskExecution → 加载 YAML → 构建 Canvas → 更新多个状态
- ✅ 新流程：创建 TaskExecution → 提交 Celery（基类自动处理状态）

**查询批次任务**：
```python
# 查询某批次所有任务
tasks = await session.execute(
    select(TaskExecution)
    .where(TaskExecution.workflow_id == workflow_id)
    .order_by(TaskExecution.created_at)
)

# 查询某个实体的历史
tasks = await session.execute(
    select(TaskExecution)
    .where(
        TaskExecution.entity_type == "job",
        TaskExecution.entity_id == "123"
    )
)
```

---

#### 6.4 异常处理

**任务级重试** (Celery 原生)：
- 指数退避策略 (60s, 120s, 240s)
- 可配置最大重试次数
- 区分可重试错误 (RateLimitError) 和不可重试错误 (InvalidAPIKey)

**钩子错误处理原则**：
- 钩子失败**不应**导致任务失败
- 记录日志但不抛出异常
- 状态追踪是可观测性，非核心业务逻辑

**僵尸任务清理**：
- 定时任务扫描 (每 5 分钟)
- 检测超时未更新的 `RUNNING` 任务
- 自动标记为 FAILED 并告警

---

#### 6.5 定时任务协调

系统使用 **Celery Beat** 作为定时任务调度器：

```python
{
    'quota-reset-monthly': {
        'task': 'tasks.quota.reset_monthly_quota',
        'schedule': crontab(day_of_month='1', hour='0', minute='0'),
    },
    'zombie-task-cleanup': {
        'task': 'tasks.workflow.cleanup_zombie_tasks',
        'schedule': crontab(minute='*/5'),
    },
}
```

**任务触发方式**：
1. **用户操作触发**: API 直接调用 `TaskService.submit_task()`
2. **定时任务触发**: Celery Beat 按时间表触发
3. **事件驱动触发**: 通过 Outbox Pattern 触发后续任务

---

#### 6.6 核心优势总结

| 维度 | 旧设计 | 新设计 | 改进 |
|------|-------|-------|------|
| **表数量** | 2张 (workflow + task) | 1张 (task) | 简化50% |
| **样板代码** | 多层嵌套包装器 | 零样板 | 减少2-3层缩进 |
| **状态追踪** | 手动装饰器 | 自动钩子 | 完全自动化 |
| **DB会话** | 手动获取 | 自动注入 `self.db` | 开箱即用 |
| **创建API** | 2步（workflow+task）| 1步（task） | 简化50% |
| **查询复杂度** | JOIN两表 | 单表查询 | 性能提升 |

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

### 8. API Response & Error Handling (统一响应格式)

**设计理念**：
- **统一响应结构**: 所有接口返回 `{code, message, data}` 格式
- **简化响应码**: 只定义需要前端特殊处理的场景（9个核心码）
- **零业务侵入**: Custom APIRoute 自动包装，业务代码直接返回数据
- **前端友好**: Axios 拦截器自动解包，业务层直接使用 data

---

#### 8.1 响应格式规范

**成功响应**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {...}  // 实际业务数据
}
```

**错误响应**：
```json
{
  "code": 1001,
  "message": "简历数量已达上限",
  "data": null
}
```

**分页响应**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  }
}
```

---

#### 8.2 响应码设计（简化版）

**核心原则**: 只定义需要前端特殊处理的场景

| Code | 说明 | HTTP | 前端处理场景 |
|------|------|------|-------------|
| `0` | 成功 | 200 | 正常展示数据 |
| `401` | 未登录 | 401 | 跳转登录页 |
| `419` | Token过期 | 419 | 刷新token或重新登录 |
| `403` | 无权限 | 403 | 显示权限不足提示 |
| `1001` | 简历数量超限 ⭐ | 400 | 显示升级套餐弹窗 |
| `1002` | AI配额耗尽 ⭐ | 400 | 显示充值/升级提示 |
| `400` | 请求参数错误 | 400 | 显示错误信息 |
| `404` | 资源不存在 | 404 | 显示404页面 |
| `500` | 服务器错误 | 500 | 显示错误提示 |

**说明**: ⭐ 标记的是需要自定义响应码的业务场景，其他场景直接使用 HTTP 状态码

**使用场景示例**：

```python
# 场景1：简历数量超限（需要自定义码）
if formal_count >= FORMAL_RESUME_LIMIT:
    raise BusinessError(
        "简历数量已达上限",
        response_code=ResponseCode.RESUME_LIMIT_EXCEEDED
    )

# 场景2：AI配额耗尽（需要自定义码）
if user.monthly_token_left <= 0:
    raise BusinessError(
        "AI配额已用尽",
        response_code=ResponseCode.QUOTA_EXCEEDED
    )

# 场景3：普通错误（使用HTTP状态码）
if not user:
    raise NotFoundError("用户不存在")  # 自动映射为 404
```

---

#### 8.3 后端实现机制

**Custom APIRoute 自动包装**：

```python
# 业务代码（零侵入）
@router.post("/register")
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await create_user(db, user_data)
    return user  # 直接返回数据

# CustomAPIRoute 自动包装为：
# {
#   "code": 0,
#   "message": "ok",
#   "data": {"id": "user_123", "email": "user@example.com", ...}
# }
```

**特殊场景处理**：
- **文件下载**: 返回 `Response` 对象，不包装
- **204 删除**: 返回 `None`，自动识别为 204 No Content
- **WebSocket**: 不受影响，保持原有协议

---

#### 8.4 前端 Axios 拦截器

**自动解包 data 字段**：

```typescript
// 拦截器自动处理
apiClient.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const { code, message, data } = response.data

    // 成功：自动返回 data
    if (code === 0) return data

    // 失败：抛出错误（包含 code 和 message）
    const error: any = new Error(message)
    error.code = code
    return Promise.reject(error)
  }
)

// 业务代码（直接使用）
const jobs = await getJobs({ page: 1 })
console.log(jobs.items)  // 直接访问 items，无需 jobs.data.items
```

**错误处理示例**：

```typescript
try {
  await createResume(data)
} catch (error: any) {
  if (error.code === 1001) {
    // 简历超限：显示升级弹窗
    Modal.confirm({
      title: '简历数量已达上限',
      content: '升级为 VIP 可创建更多简历',
      onOk: () => router.push('/upgrade')
    })
  } else if (error.code === 1002) {
    // 配额耗尽：显示充值提示
    showQuotaRechargeModal()
  } else {
    // 其他错误：显示通用提示
    message.error(error.message)
  }
}
```

---

#### 8.5 核心优势

| 维度 | 传统方案 | 新方案 | 改进 |
|------|---------|-------|------|
| **响应码数量** | 无业务码或36+个 | 9个精简码 | 维护成本↓75% |
| **业务代码** | 手动包装响应 | 直接返回数据 | 零侵入 |
| **前端处理** | 手动解包data | 自动解包 | 简化调用 |
| **错误精度** | 字符串匹配 | 业务码匹配 | 健壮可靠 |
| **特殊场景** | 需要特殊处理 | 自动识别 | 无需关注 |

---

## 模块间协作流程

### 完整申请流程示例（简化后）

```
1. 用户在 Job 详情页点击"申请"
   ↓
2. Application Module 创建申请 (status: Pending)
   ↓
3. Task Module 提交任务
   - TaskService.submit_task(task_type=TAILOR_RESUME)
   - TaskService.submit_task(task_type=GENERATE_COVER_LETTER)
   - 两个任务共享同一个 workflow_id
   ↓
4. Celery Workers 并行执行（DBTrackingTask 自动追踪状态）
   - tailor_resume_task (使用 self.db)
   - generate_cover_letter_task (使用 self.db)
   ↓
5. Resume Module 创建定制文档
   - 创建 Document (parentId: 模板Document.id, rootId: 新UUID)
   - 创建 Document (parentId: null, rootId: 新UUID)
   ↓
6. DBTrackingTask 自动更新任务状态
   - on_success 钩子：标记 SUCCESS，保存 output_data
   ↓
7. Application Module 更新状态 (status: Ready)
   - 关联定制文档 (resumeDocumentId, coverLetterDocumentId)
   - 记录时间线事件
   ↓
8. WebSocket Gateway 推送完成通知
   ↓
9. 前端展示定制材料
```

**对比旧流程**：
- ❌ 旧流程：创建 WorkflowExecution → 创建多个 TaskExecution → 加载 YAML → 手动状态管理
- ✅ 新流程：直接提交 Task → 基类自动处理状态 → 简洁清晰

---

## 核心设计模式

**1. 双层 Celery Task 基类模式**：
```
关注点分离：异步执行 vs 状态追踪

AsyncBaseTask (第一层)
  • 解决：Celery 同步调用 + async 函数 + 数据库会话管理
  • 提供：self.db 属性，自动会话生命周期
  • 适用：所有需要数据库访问的异步任务

DBTrackingTask (第二层)
  • 解决：任务状态追踪、执行时间记录、错误追溯
  • 继承：AsyncBaseTask 所有能力
  • 提供：自动状态更新钩子
  • 适用：需要追踪的业务任务
```

**2. Document 链式版本模式**：
```
所有文档内容 (简历/求职信) 统一存储在 Document 表
- 链式版本：rootId 聚合文档家族，parentId 追溯内容来源
- 内容哈希去重：contentHash 支持幂等判断和缓存
- 跨家族派生：定制简历的 parentId 指向模板，表示内容来源
- 业务元数据分离：metadata JSON 字段由业务层自定义
```

**3. 软删除模式**：
```
关键业务实体 (Application, Resume) 采用软删除
- isDeleted + deletedAt 字段
- 支持恢复操作
- 保留历史数据用于审计
- Document 表不处理软删除，由业务层管理
```

**4. 时间线记录模式**：
```
Application 关联 TimelineEvent[]
- 记录所有状态变更
- 记录用户备注
- 支持审计追踪
```

**5. 极简任务追踪模式**：
```
单表设计 + workflow 逻辑分组
- 去掉 workflow_executions 表
- workflow_id 只是 UUID 分组标识
- task 是唯一执行单元
- 通过 entity_type + entity_id 直接关联业务实体
```

**6. 统一响应格式模式**：
```
Custom APIRoute 自动包装 + 简化响应码

后端层：
  • Custom APIRoute 拦截响应并自动包装为 {code, message, data}
  • 业务代码零侵入，直接返回数据或抛异常
  • 只定义9个核心响应码（需要特殊处理的场景）
  • 其他场景使用标准 HTTP 状态码

前端层：
  • Axios 拦截器自动解包 data 字段
  • 业务代码直接使用数据，无需 response.data.data
  • 通过 error.code 精确匹配业务场景
  • 特殊场景（1001/1002）触发定制 UI
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

enum ApplicationResolution {
  ACTIVE              // still actionable in the main queue
  JOB_CLOSED          // posting closed before submission
  USER_SKIPPED        // user intentionally removed it from the active queue
  STALE_NO_RESPONSE   // reserved for future automation; not used in first rollout
}

enum TaskStatus {
  PENDING         // 等待执行
  RUNNING         // 执行中
  SUCCESS         // 成功
  FAILED          // 失败
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

### documents (链式版本模型)
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

### seek_jobs (只读数据源)
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
  tailoring_level TEXT NOT NULL DEFAULT 'light',
  status application_status NOT NULL DEFAULT 'Pending',
  resolution application_resolution NOT NULL DEFAULT 'ACTIVE',
  resolved_at TIMESTAMPTZ,
  resolution_note TEXT,
  resume_document_id TEXT,
  cover_letter_document_id TEXT,
  resume_verified BOOLEAN NOT NULL DEFAULT FALSE,
  cover_letter_verified BOOLEAN NOT NULL DEFAULT FALSE,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  CONSTRAINT fk_applications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_applications_job FOREIGN KEY (job_id) REFERENCES seek_jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_applications_source_resume FOREIGN KEY (source_resume_id) REFERENCES resumes(id) ON DELETE SET NULL,
  CONSTRAINT fk_applications_resume_doc FOREIGN KEY (resume_document_id) REFERENCES documents(id) ON DELETE SET NULL,
  CONSTRAINT fk_applications_cover_letter_doc FOREIGN KEY (cover_letter_document_id) REFERENCES documents(id) ON DELETE SET NULL,
  CONSTRAINT uq_applications_user_job UNIQUE (user_id, job_id)
);

CREATE INDEX idx_applications_user_updated_desc ON applications (user_id, updated_at DESC);
CREATE INDEX idx_applications_user_status_deleted ON applications (user_id, status, is_deleted);
CREATE INDEX idx_applications_user_resolution_updated_desc ON applications (user_id, resolution, updated_at DESC);
CREATE INDEX idx_applications_user_deleted ON applications (user_id, is_deleted);
CREATE INDEX idx_applications_status ON applications (status);
CREATE INDEX idx_applications_resolution ON applications (resolution);
CREATE INDEX idx_applications_resume_document_id ON applications (resume_document_id);
CREATE INDEX idx_applications_cover_letter_document_id ON applications (cover_letter_document_id);
```

#### Application lifecycle rules

- `status` tracks pipeline progress only.
- `resolution` tracks whether the application remains actionable.
- `Offer` and `Rejected` stay in `status` and must not be duplicated in `resolution`.
- First-rollout `resolution` values:
  - `ACTIVE`
  - `JOB_CLOSED`
  - `USER_SKIPPED`
  - `STALE_NO_RESPONSE` reserved for future automatic aging logic
- Default applications list behavior should filter to `resolution = ACTIVE`.
- `Mark as Job Closed` replaces the previous application-level expired toggle wording and must:
  - set `seek_jobs.manual_expired = true`
  - set `applications.resolution = JOB_CLOSED`
  - preserve the current pipeline `status`
- Historical backfill on migration:
  - locate manually expired jobs
  - update linked applications in `Pending`, `Tailoring`, or `Ready`
  - set `resolution = JOB_CLOSED`
  - keep submitted applications (`Applied` and after) unchanged

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

### task_executions
```sql
CREATE TABLE task_executions (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  user_id TEXT,
  task_type TEXT NOT NULL,
  task_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING',
  input_data JSONB,
  output_data JSONB,
  error_message TEXT,
  celery_task_id TEXT,
  worker_id TEXT,
  execution_time_ms INTEGER,
  retry_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  CONSTRAINT fk_task_executions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 索引设计
CREATE INDEX idx_task_executions_workflow_id ON task_executions (workflow_id);
CREATE INDEX idx_task_executions_entity ON task_executions (entity_type, entity_id);
CREATE INDEX idx_task_executions_status ON task_executions (status);
CREATE INDEX idx_task_executions_user_id ON task_executions (user_id);
CREATE INDEX idx_task_executions_entity_type_task ON task_executions (entity_type, entity_id, task_type, created_at DESC);
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
  task_id TEXT,
  workflow_id TEXT,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  cache_write_tokens INTEGER NOT NULL DEFAULT 0,
  estimated_cost NUMERIC(10,6) NOT NULL,
  operation TEXT NOT NULL,
  object_id TEXT,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_ai_usage_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_ai_usage_task FOREIGN KEY (task_id) REFERENCES task_executions(id) ON DELETE SET NULL
);

CREATE INDEX idx_ai_usage_user_timestamp ON ai_usage (user_id, timestamp);
CREATE INDEX idx_ai_usage_user_operation ON ai_usage (user_id, operation);
CREATE INDEX idx_ai_usage_task_id ON ai_usage (task_id);
CREATE INDEX idx_ai_usage_workflow_id ON ai_usage (workflow_id);
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
