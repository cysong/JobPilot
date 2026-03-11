# Celery 任务系统重构方案（从当前 AsyncBaseTask 迁移到理想架构）

## 1. 背景与目标

当前 JobPilot 的 Celery 任务系统以 `AsyncBaseTask/DBTrackingTask` 为核心，默认 worker pool 为 `solo`。  
目标是在项目未上线阶段，直接切换到更理想、可维护、线程安全的架构，并支持 `threads` 模式稳定运行。

本文档覆盖：

1. 当前方案现状与已实现能力
2. 新方案（理想方案）设计
3. 两种方案对比（功能、优缺点、缺失能力）
4. 迁移实施路径（可落地步骤）
5. 新方案潜在问题与应对策略

---

## 2. 当前方案现状分析

### 2.1 当前核心实现

- Worker 启动入口：`backend/run_celery_worker.py`
  - 默认 `--pool=solo`
  - 支持 `--concurrency`、`--prefetch-multiplier` 等参数
- Celery 配置：`backend/app/core/celery_app.py`
  - Redis broker + backend
  - 自动发现任务 + 全局任务信号（retry/failure/success）
- 生命周期与事件循环：`backend/app/core/celery_lifecycle.py`
  - 维护进程级全局 event loop（`_loop`）
- 任务基类：`backend/app/modules/workflow/tasks_base.py`
  - `AsyncBaseTask`：支持 async task + 自动注入 `self.db`
  - `DBTrackingTask`：通过 hook 写入 `task_executions` 状态
- 任务管理：`backend/app/modules/workflow/service.py`
  - 任务提交、顺序任务链、监控、重试、统计

### 2.2 当前已实现功能（代码层面）

1. 统一任务元数据模型
- `TaskType` 枚举集中定义任务路径、默认重试次数、超时等。

2. 任务状态跟踪（DB）
- 支持 `PENDING -> RUNNING -> SUCCESS/FAILED`。
- 记录 `retry_count`、`worker_id`、`execution_time_ms`、`error_message`。

3. 重试机制
- 任务基类有 autoretry 配置与异常分类排除。
- 管理端支持手动重试（包括 stale 检测和 broker presence 检测）。

4. 顺序任务编排
- `TaskService.submit_sequential_tasks()` 使用 Celery `chain`。
- 任务与 workflow 关系、步骤序号可追踪。

5. 任务监控与统计
- 基于 inspect API 聚合 worker 状态。
- 支持任务分页、筛选、失败率/耗时/成本统计。

6. AI 调用观测
- `AICall` 记录模型调用成本、耗时、状态。

### 2.3 当前方案在 `threads` 下的关键风险

1. 全局 event loop 共享风险
- 当前使用进程级 `_loop` + `run_until_complete`。
- 在线程池下，多线程访问单 loop 会产生竞争和运行时错误。

2. Task 实例共享可变状态风险
- `self._db_session`、`self._start_time` 存在实例字段。
- 线程并发时字段会互相覆盖，导致会话串扰/耗时错误。

3. hook 中“线程套线程”执行协程复杂
- `DBTrackingTask._run_db_coro` 在 loop 运行时再开线程跑 `asyncio.run`。
- 错误路径复杂，维护难，线上定位困难。

4. 业务与任务框架耦合过高
- 大量业务逻辑依赖 `self.db`、`self.request`。
- 单测和复用困难。

---

## 3. 新方案（理想方案）设计

## 3.1 设计原则

1. Celery task 保持同步入口（`def`），避免重写 `Task.__call__`。
2. 业务逻辑保持 async（use case 层），复用现有 async repository。
3. 用统一 Runner 承担 session、事务、状态更新、重试映射，消除样板代码。
4. 去除任务实例可变状态，全部上下文显式化。
5. 幂等优先，保障 at-least-once 投递下的数据一致性。

## 3.2 目标架构

建议新增模块：

- `app/modules/workflow/task_runner.py`
  - `run_tracked_task(...)`
  - `run_simple_task(...)`
- `app/modules/workflow/task_context.py`
  - `TaskContext`（task_id、celery_task_id、hostname、retry_count、logger fields）
- `app/modules/workflow/task_state_service.py`
  - 原子状态更新接口（running/success/failed/retrying）
- `app/modules/workflow/idempotency.py`
  - 幂等键生成与校验

执行模式：

1. Celery 同步任务函数（薄壳）
2. 调用统一 runner
3. runner 内部 `asyncio.run(_execute())`
4. `_execute()` 内创建 `AsyncSession` + 调用 async usecase
5. runner 统一处理提交/回滚/状态更新/日志/异常分类

## 3.3 业务代码写法（目标）

当前业务不直接依赖 `self.db`，而是写成：

- `async def analyze_job_usecase(ctx: TaskContext, db: AsyncSession, job_id: int, ...) -> dict`

Celery 任务仅负责参数接收和调用 runner：

- `def analyze_job_task(self, task_id: str, job_id: int): return run_tracked_task(...)`

这样可保留 async 数据访问能力，同时避免每个任务手写样板事务代码。

## 3.4 线程池运行配置建议（初始值）

- `pool=threads`
- `concurrency=4~8`（按 CPU 和外部 API 限流调节）
- `worker_prefetch_multiplier=1`
- `task_acks_late=true`
- `task_reject_on_worker_lost=true`
- 统一设置 soft/hard time limit（按任务类型）

---

## 4. 当前方案 vs 新方案对比

## 4.1 功能覆盖对比

| 维度 | 当前方案 | 新方案 |
|---|---|---|
| async DB 调用 | ✅ | ✅ |
| 任务状态跟踪 | ✅（hook + 基类） | ✅（runner + state service） |
| 自动重试 | ✅（基类） | ✅（统一异常映射） |
| 顺序链路 | ✅ | ✅ |
| worker 线程安全 | ⚠️（高风险） | ✅（无共享可变状态） |
| 业务代码冗余 | ⚠️（中） | ✅（runner 收口） |
| 可测试性 | ⚠️（耦合 Celery Task） | ✅（usecase 可独测） |
| 可维护性 | ⚠️（魔法较多） | ✅（职责清晰） |

## 4.2 优缺点对比

### 当前方案优点

1. 已经可运行，且已有管理端和统计能力。
2. 对业务任务改造成本短期较低。

### 当前方案缺点

1. 对 `threads` 模式不友好（共享 loop/实例状态）。
2. 基类逻辑复杂，故障定位成本高。
3. 业务与任务运行时耦合深，长期演进成本高。

### 新方案优点

1. 线程安全边界清晰，`threads` 下可稳定扩并发。
2. 业务逻辑纯化，测试与复用能力明显提升。
3. 事务、状态、重试策略集中治理，行为一致性更好。

### 新方案代价

1. 需要一次性结构性重构（task 基类和任务函数迁移）。
2. 需要补充一套完善的回归与压测。

## 4.3 未实现能力（两边共性）

当前和目标方案都建议补齐但暂未完整实现：

1. 系统级幂等键规范与唯一索引矩阵（按任务类型细化）。
2. 失败任务死信队列与自动告警联动。
3. 端到端压测基准（吞吐、延迟、失败率）与容量曲线。
4. 任务 SLA 分级调度（高/中/低优先级队列治理）。

---

## 5. 迁移实施路径（从当前方案切换）

## 5.1 Phase 0：文档与配置基线

1. 更新架构文档（新增任务执行层设计图、边界说明）。
2. 在 `.env.example` 补充 Celery 关键参数模板。
3. 明确异常分类标准（可重试 vs 不可重试）。

交付物：

- 新架构设计文档（本文件）
- 配置清单
- 异常分类清单

## 5.2 Phase 1：基础设施落地（不迁业务）

1. 新增 `task_runner.py`、`task_context.py`、`task_state_service.py`。
2. 提供统一 API：
   - `run_tracked_task()`
   - `run_simple_task()`
3. 引入统一日志字段注入（task_id/celery_task_id/worker/retry）。

验证：

1. 新 runner 单元测试（成功/失败/重试/超时）。
2. 数据库状态一致性测试。

## 5.3 Phase 2：任务分批迁移

按风险从低到高迁移：

1. 定时任务/简单任务（`AsyncBaseTask` 使用者）
2. 单步追踪任务（如 `analyze_job_task`、`analyze_resume_task`）
3. 复杂链路任务（application 初始化与链路任务）

每迁移一个任务类型执行：

1. 功能回归
2. 重试回归
3. 状态一致性回归

## 5.4 Phase 3：移除旧基类与生命周期实现

1. 删除 `AsyncBaseTask` 和 `DBTrackingTask` 的执行魔法路径。
2. 清理 `celery_lifecycle.py` 的全局 loop 维护逻辑。
3. 保留最小生命周期钩子（仅资源关闭）。

## 5.5 Phase 4：切换 worker 到 threads

1. `CELERY_WORKER_POOL=threads`
2. 初始 `concurrency=4` 灰度
3. 观察 24-48 小时后按指标提升至 6/8

观测指标：

1. 任务成功率、平均耗时、P95/P99
2. 重试率和失败类型分布
3. 数据库连接池占用
4. 外部 API 429/timeout 比率

## 5.6 Phase 5：收尾

1. 更新 `docs/progress.md`
2. 补充 `docs/issues.md` 中迁移期问题与解决记录
3. 固化运行手册（并发调整/故障排查）

---

## 6. 新方案可能问题与应对策略

## 6.1 `asyncio.run` 开销与频繁创建 loop

问题：
- 每个任务都创建/销毁 loop，有开销。

应对：
1. 先验证实际瓶颈（多为 I/O，不在 loop 创建）。
2. 若成为瓶颈，再引入“每线程 loop 缓存”优化（仅在 runner 内实现，业务无感）。

## 6.2 数据库连接压力上升

问题：
- `threads` 并发升高后 asyncpg 连接占用上升。

应对：
1. 调整 SQLAlchemy pool 参数（`pool_size/max_overflow`）。
2. 限制 worker 并发与 DB 池比例。
3. 对重查询任务增加批处理与分页策略。

## 6.3 外部 AI API 限流（429）放大

问题：
- 并发提升会触发更高 429 率，导致重试风暴。

应对：
1. 在异常分类中将 429 纳入指数退避重试。
2. 任务级限流（按 agent/model 配额）。
3. 对高成本任务做并发闸门（semaphore/queue routing）。

## 6.4 状态更新与业务事务一致性

问题：
- 业务成功但状态更新失败，或反向情况。

应对：
1. 由 runner 统一定义“状态更新失败处理策略”。
2. 状态更新与业务提交顺序固定（先业务提交，再状态最终写入）。
3. 加入异常补偿任务（定期修复异常状态）。

## 6.5 迁移期双机制并存导致行为不一致

问题：
- 部分任务走旧基类，部分走新 runner，行为难统一。

应对：
1. 迁移期间明确“唯一真相”规范（重试/状态均以新策略为准）。
2. 控制迁移窗口，尽量短周期完成。
3. 每批迁移后清理旧路径，避免长期双栈。

---

## 7. 建议的最终落地状态（目标）

1. Celery Task 函数：同步薄壳，仅解析参数与调用 runner。
2. 业务逻辑：纯 async usecase，依赖显式上下文，不依赖 `self`。
3. 任务状态：由 `TaskStateService` 统一更新。
4. 幂等：任务类型级别 idempotency key + 唯一索引。
5. worker：`threads` 作为 I/O 主力；CPU 任务独立 `prefork` 队列（如未来出现）。

---

## 8. 执行建议（优先级）

1. 先实现 Runner 与状态服务（不改业务）。
2. 先迁移 1-2 个任务类型做样板（Job/Resume Analysis）。
3. 完成回归后批量迁移剩余任务。
4. 移除旧基类，再切 threads 灰度放量。

该顺序可以最大程度降低一次性重构风险，同时快速验证理想架构收益。
