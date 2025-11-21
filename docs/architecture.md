# JobPilot 系统架构设计

## 技术栈

### 前端
- **框架**: React 18 + Vite 5
- **语言**: TypeScript 5.x
- **UI组件**: shadcn/ui + Tailwind CSS
- **状态管理**: Zustand
- **路由**: React Router v6
- **表单**: React Hook Form + Zod
- **HTTP客户端**: Axios + TanStack Query (React Query)
- **实时通信**: Socket.IO Client
- **Markdown编辑**: React-Markdown-Editor-Lite
- **拖拽**: @hello-pangea/dnd
- **PDF生成**: jsPDF / react-pdf

### 后端
- **框架**: FastAPI 0.109+
- **语言**: Python 3.11+
- **ORM**: SQLAlchemy 2.0 (Async) + Alembic
- **数据库**: PostgreSQL 15+
- **缓存**: Redis 7+ (aioredis)
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
│   │   │   ├── models.py             # Job/JobAnalysis/JobMatch 模型
│   │   │   ├── schemas.py            # Job 请求/响应模式
│   │   │   ├── tasks.py              # Job 分析 Celery 任务
│   │   │   └── utils.py              # Job 工具函数
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
│   │   │   ├── models.py             # Resume/Document/DocumentVersion 模型
│   │   │   ├── schemas.py            # 简历请求/响应模式
│   │   │   └── utils.py              # Markdown解析、PDF生成
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
├── pyproject.toml                    # Poetry 依赖管理
├── alembic.ini                       # Alembic 配置
├── .env.example                      # 环境变量示例
└── README.md
```

---

## 核心模块设计

### 1. Auth Module (认证授权)

**功能覆盖**：
- ✅ 用户注册/登录
- ✅ JWT Token管理
- ✅ 角色权限控制 (普通用户/VIP/管理员)
- ✅ 配额验证

**关键代码**：
```typescript
// auth.guard.ts
@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {}

@Injectable()
export class RolesGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.get<Role[]>('roles', context.getHandler());
    const { user } = context.switchToHttp().getRequest();
    return requiredRoles.some(role => user.role === role);
  }
}

// quota.guard.ts
@Injectable()
export class QuotaGuard implements CanActivate {
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const user = request.user;

    // 检查配额
    const usage = await this.quotaService.getMonthlyUsage(user.id);
    const limit = await this.quotaService.getQuotaLimit(user.role);

    if (usage.applications >= limit.maxApplications) {
      throw new ForbiddenException('Monthly application quota exceeded');
    }

    return true;
  }
}
```

---

### 2. Job Module (职位管理)

**功能覆盖**：
- ✅ Job列表/详情 (只读)
- ✅ 服务器端分页 (每页20条)
- ✅ 多维度筛选 (地点/类型/公司/时间)
- ✅ 关键词搜索 (PostgreSQL全文搜索)
- ✅ 匹配度/紧急度展示

**API设计**：
```typescript
// jobs.controller.ts
@Controller('jobs')
export class JobsController {
  @Get()
  async findAll(@Query() filters: JobFiltersDto, @CurrentUser() user: User) {
    return this.jobsService.findAll(filters, user.id);
  }

  @Get(':id')
  async findOne(@Param('id') id: string, @CurrentUser() user: User) {
    return this.jobsService.findOne(id, user.id);
  }

  @Get(':id/similar')
  async findSimilar(@Param('id') id: string) {
    return this.jobsService.findSimilarJobs(id);
  }
}

// jobs.service.ts
async findAll(filters: JobFiltersDto, userId: string) {
  const { page = 1, limit = 20, location, type, company, keyword } = filters;

  const where = {
    deletedAt: null,
    ...(location && { location: { in: location } }),
    ...(type && { employmentType: type }),
    ...(company && { company: { in: company } }),
    ...(keyword && {
      OR: [
        { title: { search: keyword } },
        { descriptionMarkdown: { search: keyword } }
      ]
    })
  };

  const [jobs, total] = await Promise.all([
    this.prisma.job.findMany({
      where,
      include: {
        analysis: true,
        matches: {
          where: { userId },
          select: { matchScore: true, urgencyScore: true, bestMatchedResumeId: true }
        }
      },
      orderBy: { publishedAt: 'desc' },
      skip: (page - 1) * limit,
      take: limit,
    }),
    this.prisma.job.count({ where })
  ]);

  return {
    data: jobs,
    meta: {
      total,
      page,
      lastPage: Math.ceil(total / limit)
    }
  };
}
```

---

### 3. Application Module (申请管理)

**功能覆盖**：
- ✅ 申请CRUD
- ✅ 状态流转 (Pending → Tailoring → Ready → Applied → Interviewing → Offer/Rejected)
- ✅ 时间线记录
- ✅ 批量操作 (批量标记Applied)
- ✅ 材料版本化

**关键实现**：
```typescript
// applications.service.ts
async create(userId: string, createDto: CreateApplicationDto) {
  // 1. 检查唯一性
  const existing = await this.prisma.application.findUnique({
    where: {
      userId_jobId: { userId, jobId: createDto.jobId }
    }
  });

  if (existing) {
    if (existing.deletedAt) {
      // 恢复软删除的申请
      return this.restore(existing.id);
    }
    throw new ConflictException('Application already exists');
  }

  // 2. 创建申请
  const application = await this.prisma.application.create({
    data: {
      userId,
      jobId: createDto.jobId,
      userId,
      jobId: createDto.jobId,
      sourceResumeId: createDto.resumeId,
      tailoringLevel: createDto.tailoringLevel || 'Light', // Default to Light if not specified
      status: 'Pending',
      timeline: {
        create: {
          event: 'created',
          timestamp: new Date(),
        }
      }
    }
  });

  // 3. 触发AI工作流 (入队到BullMQ)
  await this.queueService.addApplicationJob({
    applicationId: application.id,
    resumeId: createDto.resumeId,
    customRequirements: createDto.customRequirements
  });

  return application;
}

async updateStatus(id: string, status: ApplicationStatus, note?: string) {
  const application = await this.prisma.application.update({
    where: { id },
    data: {
      status,
      timeline: {
        create: {
          event: `status_changed_to_${status}`,
          note,
          timestamp: new Date(),
        }
      }
    }
  });

  // 如果状态变为Interviewing,触发面试准备
  if (status === 'Interviewing') {
    await this.queueService.addInterviewPrepJob({
      applicationId: id,
      userId: application.userId,
      jobId: application.jobId
    });
  }

  return application;
}

async batchUpdateStatus(ids: string[], status: ApplicationStatus) {
  return this.prisma.application.updateMany({
    where: { id: { in: ids } },
    data: { status }
  });
}
```

---

### 4. AI Agent Module (核心AI能力)

**功能覆盖**：
- ✅ Job分析 (HTML→Markdown、翻译、技能提取)
- ✅ 简历定制
- ✅ Cover Letter生成
- ✅ 质量检查
- ✅ 面试准备材料生成
- ✅ 简历推荐

**Claude Agent实现**：
```typescript
// ai-agent.service.ts
import Anthropic from '@anthropic-ai/sdk';

@Injectable()
export class AiAgentService {
  private anthropic: Anthropic;

  constructor(
    private configService: ConfigService,
    private usageTracker: UsageTrackerService
  ) {
    this.anthropic = new Anthropic({
      apiKey: this.configService.get('ANTHROPIC_API_KEY'),
    });
  }

  async runAgent(config: AgentConfig) {
    const { systemPrompt, messages, tools, userId } = config;

    let continueLoop = true;
    const toolResults: any[] = [];

    while (continueLoop) {
      const response = await this.anthropic.messages.create({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 4096,
        system: systemPrompt,
        messages,
        tools,
      });

      // 追踪使用量
      await this.usageTracker.track(userId, {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
      });

      if (response.stop_reason === 'tool_use') {
        // 处理工具调用
        for (const content of response.content) {
          if (content.type === 'tool_use') {
            const result = await this.executeTool(content.name, content.input);

            messages.push({
              role: 'assistant',
              content: response.content
            });

            messages.push({
              role: 'user',
              content: [{
                type: 'tool_result',
                tool_use_id: content.id,
                content: JSON.stringify(result)
              }]
            });

            toolResults.push({ tool: content.name, result });
          }
        }
      } else {
        continueLoop = false;

        const finalText = response.content
          .filter(c => c.type === 'text')
          .map(c => c.text)
          .join('\n');

        return {
          success: true,
          response: finalText,
          toolResults,
          usage: response.usage
        };
      }
    }
  }

  private async executeTool(toolName: string, input: any) {
    // 工具路由分发
    switch (toolName) {
      case 'extract_skills':
        return this.jobAnalysisTools.extractSkills(input);
      case 'translate_text':
        return this.translationTools.translate(input);
      case 'tailor_resume':
        // input should include { strategy: 'Deep' | 'Light' }
        return this.resumeTools.tailor(input);
      case 'generate_cover_letter':
        return this.coverLetterTools.generate(input);
      case 'quality_check':
        return this.qualityCheckTools.check(input);
      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
  }
}
```

---

### 5. Queue Module (任务队列)

**功能覆盖**：
- ✅ Job分析定时任务
- ✅ 申请材料生成
- ✅ 面试准备生成
- ✅ 匹配度预计算
- ✅ 失败重试

**BullMQ集成**：
```typescript
// queue.module.ts
@Module({
  imports: [
    BullModule.forRoot({
      connection: {
        host: 'localhost',
        port: 6379,
      },
    }),
    BullModule.registerQueue(
      { name: 'job-analysis' },
      { name: 'application' },
      { name: 'interview-prep' },
      { name: 'match-score' }
    ),
  ],
  providers: [
    JobAnalysisProcessor,
    ApplicationProcessor,
    InterviewPrepProcessor,
    MatchScoreProcessor,
  ],
})
export class QueueModule {}

// application.processor.ts
@Processor('application')
export class ApplicationProcessor {
  @Process('generate-materials')
  async handleApplicationGeneration(job: Job<ApplicationJobData>) {
    const { applicationId, resumeId, customRequirements } = job.data;

    try {
      // 更新进度
      await job.updateProgress({ stage: 'research', status: 'processing' });

      // 运行Agent工作流
      const result = await this.aiAgentService.generateApplicationMaterials({
        applicationId,
        resumeId,
        customRequirements
      });

      // 保存结果
      await this.prisma.application.update({
        where: { id: applicationId },
        data: {
          status: 'Ready',
          tailoredResumeContent: result.tailoredResume,
          coverLetterContent: result.coverLetter,
          qualityCheckResults: result.qualityCheck,
        }
      });

      return result;

    } catch (error) {
      await job.log(`Failed: ${error.message}`);
      throw error; // BullMQ会自动重试
    }
  }
}
```

---

### 6. WebSocket Gateway (实时通信)

**功能覆盖**：
- ✅ 任务进度实时推送
- ✅ 申请状态变更通知
- ✅ 配额预警

```typescript
// websocket.gateway.ts
@WebSocketGateway({
  cors: { origin: 'http://localhost:5173' }
})
export class WebSocketGateway {
  @WebSocketServer()
  server: Server;

  // 加入申请房间
  @SubscribeMessage('join-application')
  handleJoinApplication(
    @MessageBody() applicationId: string,
    @ConnectedSocket() client: Socket
  ) {
    client.join(`application:${applicationId}`);
  }

  // 发送进度更新
  emitProgress(applicationId: string, progress: ProgressUpdate) {
    this.server.to(`application:${applicationId}`).emit('progress', progress);
  }

  // 发送状态变更
  emitStatusChange(applicationId: string, status: ApplicationStatus) {
    this.server.to(`application:${applicationId}`).emit('status-change', status);
  }
}
```

---

## 数据库Schema (Prisma)

```prisma
// schema.prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

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

enum DocumentType {
  Resume         // 简历模板
  TailoredResume // 定制简历
  CoverLetter    // 求职信
}

enum DocumentFormat {
  Markdown
  HTML
  PlainText
}

// ============================================
// 核心文档管理模型
// ============================================

model Document {
  id                   String         @id @default(cuid())
  docType              DocumentType   // 文档类型（创建后不可变）
  sourceDocumentId     String?        // 源文档ID（用于追溯）
  sourceVersionId      String?        // 源文档版本ID
  latestVersionNum     Int            @default(1)
  latestVersionContent String         @db.Text
  format               DocumentFormat @default(Markdown) // 格式（创建后不可变）

  createdBy            String
  createdAt            DateTime       @default(now())
  updatedAt            DateTime       @updatedAt
  updatedBy            String
  isDeleted            Boolean        @default(false) // 软删除标记
  deletedAt            DateTime?      // 软删除时间

  // 关联关系
  creator              User             @relation("DocumentCreator", fields: [createdBy], references: [id])
  updater              User             @relation("DocumentUpdater", fields: [updatedBy], references: [id])
  sourceDocument       Document?        @relation("DocumentDerivation", fields: [sourceDocumentId], references: [id], onDelete: SetNull)
  derivedDocuments     Document[]       @relation("DocumentDerivation")
  versions             DocumentVersion[]

  // 业务层关联（一对一）
  resume                       Resume?
  tailoredResumeApplications   Application[] @relation("TailoredResumeDocument")
  coverLetterApplications      Application[] @relation("CoverLetterDocument")

  @@index([docType, isDeleted, createdBy])
  @@index([sourceDocumentId])
  @@index([createdAt(sort: Desc)])
  @@index([isDeleted])
  @@map("documents")
}

model DocumentVersion {
  id             String   @id @default(cuid())
  documentId     String
  versionNum     Int
  content        String   @db.Text
  changeSummary  String?  // AI修改摘要或用户备注
  createdBy      String
  createdAt      DateTime @default(now())

  document       Document @relation(fields: [documentId], references: [id], onDelete: Cascade)
  creator        User     @relation(fields: [createdBy], references: [id])

  @@unique([documentId, versionNum])
  @@index([documentId, createdAt(sort: Desc)])
  @@map("document_versions")
}

// ============================================
// 用户与认证
// ============================================

model User {
  id                String   @id @default(cuid())
  email             String   @unique
  passwordHash      String
  role              Role     @default(USER)
  preferences       Json?    // 定制需求预设 {resumeCustomization, coverLetterStyle}
  linkedinConnected Boolean  @default(false)
  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt

  // 关联关系
  resumes              Resume[]
  applications         Application[]
  skills               UserSkill[]
  jobMatches           JobMatch[]
  aiUsage              AiUsage[]
  interviewPrep        InterviewPrep[]

  // 文档创建/更新关系
  createdDocuments     Document[]        @relation("DocumentCreator")
  updatedDocuments     Document[]        @relation("DocumentUpdater")
  documentVersions     DocumentVersion[]

  @@map("users")
}

// ============================================
// 简历模板管理
// ============================================

model Resume {
  id         String    @id @default(cuid())
  userId     String
  documentId String    @unique // 关联到Document表
  title      String    // 简历名称（用户内唯一）
  isDraft    Boolean   @default(true) // 草稿/正式版本
  createdAt  DateTime  @default(now())
  updatedAt  DateTime  @updatedAt
  isDeleted  Boolean   @default(false) // 软删除标记
  deletedAt  DateTime? // 软删除时间

  user       User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  document   Document  @relation(fields: [documentId], references: [id], onDelete: Cascade)

  // 反向关联：哪些申请使用了此简历模板
  applications Application[]

  @@unique([userId, title])
  @@index([userId, isDraft, isDeleted])
  @@index([userId, isDeleted])
  @@map("resumes")
}

// ============================================
// Job职位管理（只读表，由外部系统维护）
// 注意：seek_jobs表由外部爬虫系统维护，JobPilot只读访问
// ============================================

model Job {
  id                         Int       @id @default(autoincrement())
  sourceId                   String    @unique @map("source_id")
  title                      String    @db.VarChar(500)
  abstract                   String?   @db.Text
  content                    String?   @db.Text
  status                     String?   @db.VarChar(50)
  isExpired                  Boolean?  @default(false) @map("is_expired")
  isLinkOut                  Boolean?  @default(false) @map("is_link_out")
  isVerified                 Boolean?  @default(false) @map("is_verified")
  phoneNumber                String?   @db.VarChar(50) @map("phone_number")
  shareLink                  String?   @db.Text @map("share_link")
  listedAt                   DateTime? @map("listed_at") @db.Timestamptz(6)
  expiresAt                  DateTime? @map("expires_at") @db.Timestamptz(6)

  // 薪资信息
  salaryLabel                String?   @db.VarChar(200) @map("salary_label")

  // 工作类型
  workTypesLabel             String?   @db.VarChar(100) @map("work_types_label")
  workTypeIds                String?   @db.VarChar(50) @map("work_type_ids")

  // 地点信息
  locationLabel              String?   @db.VarChar(200) @map("location_label")
  locationArea               String?   @db.VarChar(100) @map("location_area")
  locationCity               String?   @db.VarChar(100) @map("location_city")
  locationIds                String?   @db.Text @map("location_ids")
  countryCode                String?   @db.VarChar(10) @map("country_code")
  country                    String?   @db.VarChar(50)
  suburb                     String?   @db.VarChar(100)
  region                     String?   @db.VarChar(100)
  state                      String?   @db.VarChar(100)
  postcode                   String?   @db.VarChar(20)

  // 广告主信息
  advertiserId               String?   @db.VarChar(50) @map("advertiser_id")
  advertiserName             String?   @db.VarChar(300) @map("advertiser_name")
  advertiserIsVerified       Boolean?  @default(false) @map("advertiser_is_verified")
  advertiserRegistrationDate DateTime? @map("advertiser_registration_date") @db.Timestamptz(6)
  isPrivateAdvertiser        Boolean?  @default(false) @map("is_private_advertiser")

  // 分类信息
  classificationId           String?   @db.VarChar(20) @map("classification_id")
  classification             String?   @db.VarChar(200)
  subClassificationId        String?   @db.VarChar(20) @map("sub_classification_id")
  subClassification          String?   @db.VarChar(200) @map("sub_classification")
  classificationsLabel       String?   @db.VarChar(500) @map("classifications_label")

  // 品牌信息
  productBullets             String?   @db.Text @map("product_bullets")
  brandingId                 String?   @db.VarChar(100) @map("branding_id")
  brandingCoverUrl           String?   @db.Text @map("branding_cover_url")
  brandingThumbnailUrl       String?   @db.Text @map("branding_thumbnail_url")
  brandingLogoUrl            String?   @db.Text @map("branding_logo_url")
  displayTags                String?   @db.Text @map("display_tags")

  // 公司信息
  companyProfileId           String?   @db.VarChar(50) @map("company_profile_id")
  companyName                String?   @db.VarChar(300) @map("company_name")
  companySlug                String?   @db.VarChar(200) @map("company_slug")
  companyLogo                String?   @db.Text @map("company_logo")
  companyDescription         String?   @db.Text @map("company_description")
  companyIndustry            String?   @db.VarChar(100) @map("company_industry")
  companySize                String?   @db.VarChar(100) @map("company_size")
  companyWebsite             String?   @db.Text @map("company_website")
  shouldDisplayReviews       Boolean?  @default(false) @map("should_display_reviews")

  // 标准化字段
  normalisedRoleTitle        String?   @db.VarChar(300) @map("normalised_role_title")
  normalisedOrganisationName String?   @db.VarChar(300) @map("normalised_organisation_name")
  broaderLocationName        String?   @db.VarChar(100) @map("broader_location_name")

  // 其他元数据
  sourceZone                 String?   @db.VarChar(20) @map("source_zone")
  adProductType              String?   @db.VarChar(50) @map("ad_product_type")
  hasRoleRequirements        Boolean?  @default(false) @map("has_role_requirements")
  contactPhone               String?   @db.VarChar(50) @map("contact_phone")
  contactEmail               String?   @db.VarChar(100) @map("contact_email")
  restrictedApplicationLabel String?   @db.VarChar(200) @map("restricted_application_label")

  // 时间戳
  createdAt                  DateTime? @default(now()) @map("created_at") @db.Timestamptz(6)
  updatedAt                  DateTime? @default(now()) @updatedAt @map("updated_at") @db.Timestamptz(6)

  // 关联关系（JobPilot系统新增）
  analysis                   JobAnalysis?
  applications               Application[]
  matches                    JobMatch[]

  @@index([sourceId], map: "idx_seek_jobs_source_id")
  @@index([title], map: "idx_seek_jobs_title")
  @@index([listedAt], map: "idx_seek_jobs_listed_at")
  @@index([isExpired], map: "idx_seek_jobs_is_expired")
  @@index([status], map: "idx_seek_jobs_status")
  @@index([locationCity], map: "idx_seek_jobs_location_city")
  @@index([advertiserName], map: "idx_seek_jobs_advertiser_name")
  @@index([classification], map: "idx_seek_jobs_classification")
  @@index([subClassification], map: "idx_seek_jobs_sub_classification")
  @@map("seek_jobs")
}

model JobAnalysis {
  id              String    @id @default(cuid())
  jobId           Int       @unique @map("job_id") // 关联到Job.id (Int类型)
  requiredSkills  String[]  // 必备技能
  optionalSkills  String[]  // 可选技能
  softSkills      String[]  // 软技能
  yearsExperience Int?      // 工作年限要求
  deadline        DateTime? // 申请截止日期（用于计算紧急度）
  analysisResult  String?   @db.VarChar(50) // success/failed/pending
  errorMessage    String?   @db.Text
  analyzedAt      DateTime?

  job             Job       @relation(fields: [jobId], references: [id], onDelete: Cascade)

  @@map("job_analysis")
}

model JobMatch {
  id           String   @id @default(cuid())
  userId       String
  jobId        Int      @map("job_id") // 关联到Job.id (Int类型)
  matchScore   Decimal  @db.Decimal(5, 2) // 0-100 匹配度
  urgencyScore Decimal? @db.Decimal(5, 2) // 0-100 紧急度
  bestMatchedResumeId String? @map("best_matched_resume_id") // 系统推荐的最佳简历ID
  updatedAt    DateTime @default(now()) @map("updated_at")

  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  job          Job      @relation(fields: [jobId], references: [id], onDelete: Cascade)
  bestMatchedResume Resume? @relation(fields: [bestMatchedResumeId], references: [id])

  @@unique([userId, jobId])
  @@index([userId, matchScore(sort: Desc)])
  @@index([userId, urgencyScore(sort: Desc)])
  @@map("job_matches")
}

// ============================================
// 申请管理
// ============================================

model Application {
  id                      String            @id @default(cuid())
  userId                  String            @map("user_id")
  jobId                   Int               @map("job_id") // 关联到Job.id (Int类型)
  sourceResumeId          String            @map("source_resume_id") // 用户选择的简历模板 (作为定制来源)
  tailoringLevel          String?           @map("tailoring_level") // 定制深度: "Deep", "Light"
  status                  ApplicationStatus @default(Pending)

  // 定制简历和求职信（直接存储documentId）
  resumeDocumentId        String?           @map("resume_document_id") // 定制简历的Document ID
  coverLetterDocumentId   String?           @map("cover_letter_document_id") // 求职信的Document ID

  // 质量检查标记
  resumeVerified          Boolean           @default(false) @map("resume_verified") // 简历已验证
  coverLetterVerified     Boolean           @default(false) @map("cover_letter_verified") // 求职信已验证

  createdAt               DateTime          @default(now()) @map("created_at")
  updatedAt               DateTime          @updatedAt @map("updated_at")
  isDeleted               Boolean           @default(false) @map("is_deleted") // 软删除标记
  deletedAt               DateTime?         @map("deleted_at") // 软删除时间

  user                    User              @relation(fields: [userId], references: [id], onDelete: Cascade)
  job                     Job               @relation(fields: [jobId], references: [id], onDelete: Cascade)
  sourceResume            Resume            @relation(fields: [sourceResumeId], references: [id])

  // 关联到定制文档
  resumeDocument          Document?         @relation("TailoredResumeDocument", fields: [resumeDocumentId], references: [id], onDelete: SetNull)
  coverLetterDocument     Document?         @relation("CoverLetterDocument", fields: [coverLetterDocumentId], references: [id], onDelete: SetNull)

  // 时间线
  timeline                TimelineEvent[]

  @@unique([userId, jobId])
  @@index([userId, updatedAt(sort: Desc)])
  @@index([userId, status, isDeleted])
  @@index([userId, isDeleted])
  @@index([status])
  @@index([resumeDocumentId])
  @@index([coverLetterDocumentId])
  @@map("applications")
}

model TimelineEvent {
  id            String      @id @default(cuid())
  applicationId String
  event         String      // created/status_changed/note_added/material_generated/quality_check
  note          String?     // 用户备注
  metadata      Json?       // 额外元数据（如状态变更前后值）
  timestamp     DateTime    @default(now())

  application   Application @relation(fields: [applicationId], references: [id], onDelete: Cascade)

  @@index([applicationId, timestamp(sort: Desc)])
  @@map("timeline_events")
}

// ============================================
// 技能管理
// ============================================

model UserSkill {
  id              String           @id @default(cuid())
  userId          String
  skillName       String
  proficiency     ProficiencyLevel
  skillType       String           // technical/soft/industry
  extractedFromId String?          // 来源简历ID（Resume.id）
  createdAt       DateTime         @default(now())
  updatedAt       DateTime         @updatedAt

  user            User             @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([userId, skillName])
  @@index([userId, skillType])
  @@map("user_skills")
}

// ============================================
// AI使用追踪（配额管理）
// ============================================

model AiUsage {
  id               String   @id @default(cuid())
  userId           String
  model            String   // claude-3-5-sonnet-20241022
  inputTokens      Int
  outputTokens     Int
  cacheReadTokens  Int      @default(0)
  cacheWriteTokens Int      @default(0)
  estimatedCost    Decimal  @db.Decimal(10, 6)
  operation        String   // job_analysis/resume_tailor/cover_letter/interview_prep
  objectId         String?  // 无FK，可存储 applicationId/resumeId/jobId
  timestamp        DateTime @default(now())

  user             User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, timestamp])
  @@index([userId, operation])
  @@map("ai_usage")
}
```
