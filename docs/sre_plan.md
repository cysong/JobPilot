# JobPilot SRE 改造规划

---

## 1. 背景与目标

### 1.1 个人背景

具备全栈开发能力（FastAPI + React），熟悉容器化部署与异步任务系统。当前以 JobPilot 作为核心个人项目，目标是通过系统化的 SRE 改造，将其从"能用的业务项目"升级为"可在生产环境运行、监控和扩展的系统"，以此证明 SRE 岗位所需的工程能力。

### 1.2 改造目的

| 改造前 | 改造后 |
|---|---|
| 功能导向，偏开发视角 | 系统运行视角，关注稳定性与可观测性 |
| 本地/VPS 手动部署 | 基础设施即代码，自动化部署 |
| 无指标、无告警 | Prometheus + Grafana + Alertmanager |
| 无 SLO 定义 | 明确 SLI/SLO/Error Budget |

### 1.3 目标岗位关键词分析

以下为 SRE 岗位 JD 中的高频关键词，及其在本项目中的对应实现：

| SRE JD 关键词 | 项目对应实现 | 当前状态 |
|---|---|---|
| Observability / Monitoring | Prometheus + Grafana + Alertmanager | ❌ 待实现 |
| SLO / SLI / Error Budget | 定义可用性目标与误差预算 | ❌ 待实现 |
| Infrastructure as Code (IaC) | Terraform 管理 AWS 资源 | ❌ 待实现 |
| CI/CD | GitHub Actions 自动构建/部署 | ✅ 已完成 |
| Containerization | Docker + docker-compose | ✅ 已完成 |
| On-call / Incident Response | Alertmanager + Runbook | ❌ 待实现 |
| Kubernetes / K8s | EKS 部署（可选进阶） | ❌ 可选 |
| Serverless | Lambda + SQS + EventBridge | ❌ 可选 |
| Distributed Systems | Celery + Redis 异步任务 | ✅ 已完成 |
| Cost Optimization | 方案选型与费用分析 | ✅ 本文档 |

---

## 2. 项目现状分析

### 2.1 技术栈概览

**后端：** FastAPI 0.109+ · Python 3.11 · PostgreSQL（Supabase 托管）· Redis · Celery · SQLAlchemy 2.0 · Alembic · structlog · WeasyPrint

**前端：** React 19 · TypeScript · Vite · Tailwind CSS · React Query · Zustand

**部署：** Hostinger VPS · Docker · docker-compose · Nginx · GitHub Actions

### 2.2 已具备的 SRE 基础

以下能力**已落地**，无需重复建设：

- ✅ **Docker 多阶段镜像构建** — `backend/Dockerfile`
- ✅ **生产环境 docker-compose 编排** — 4 个服务（api / worker / beat / redis）
- ✅ **CI/CD 自动化** — GitHub Actions 构建镜像、推送 GHCR、SSH 部署 VPS
- ✅ **结构化日志** — structlog，含 service / task_id / workflow_id 上下文字段
- ✅ **健康检查** — `/health` 端点 + Docker compose healthcheck
- ✅ **异步任务系统** — Celery Worker + Beat，含任务重试/失败信号处理
- ✅ **数据库迁移** — Alembic，CI 中自动执行
- ✅ **API 缓存** — fastapi-cache2[redis]

### 2.3 当前缺口

- ❌ 无指标采集（Prometheus）
- ❌ 无可视化 Dashboard（Grafana）
- ❌ 无告警规则（Alertmanager）
- ❌ 无 SLO / SLI 定义
- ❌ 无分布式追踪（OpenTelemetry）
- ❌ 无 Runbook / Incident 处理流程
- ❌ 无云基础设施管理（Terraform / AWS）

---

## 3. 基础设施部署方案对比

### 3.1 三方案概述

| | EC2（方案 A） | ECS Fargate（方案 B） | EKS（方案 C） |
|---|---|---|---|
| 部署模型 | 虚拟机，手动管 Docker | 托管容器，无需管服务器 | 托管 Kubernetes |
| 运维复杂度 | 低 | 中 | 高 |
| Terraform 价值 | 中（VPC/EC2/IAM） | 高（完整 AWS 资源图谱） | 高 |
| 适合规模 | 小型，单服务 | 中型，多服务 | 中大型，需弹性扩展 |

### 3.2 费用对比（低流量场景，<10 用户/月）

| 服务 | 方案 A EC2 | 方案 B ECS Fargate | 方案 C EKS |
|---|---|---|---|
| 计算资源 | t3.small $15 | Fargate 4任务 ~$63 | EC2 节点 ×2 ~$60 |
| EKS 控制面 | — | — | **$73（固定）** |
| PostgreSQL | Supabase 免费 $0 | RDS db.t3.micro $15 | RDS db.t3.micro $15 |
| Redis | 容器内 $0 | ElastiCache $12 | ElastiCache $12 |
| 负载均衡 | Nginx on EC2 $0 | ALB $16 | ALB $16 |
| S3 + CloudFront | $2 | $2 | $2 |
| **月合计** | **~$17** | **~$108** | **~$178** |

> 注：方案 A 保留 Supabase PostgreSQL；新 AWS 账号 Free Tier 可使第一年费用进一步降低。

### 3.3 运维复杂度对比

| 维度 | 方案 A | 方案 B | 方案 C |
|---|---|---|---|
| 服务器维护（OS/补丁） | 需要手动 | 无需 | 节点需管理 |
| 容器编排 | docker-compose | ECS Task Definition | K8s Deployment/Service |
| 扩容方式 | 手动调整 EC2 规格 | 修改 Fargate CPU/Mem | HPA 自动扩容 |
| 本地调试 | 简单（docker-compose） | 需要 AWS CLI + SAM | 需要 minikube/kind |
| 部署回滚 | 修改 image tag 重启 | ECS rolling update | kubectl rollout undo |

### 3.4 简历价值对比

| SRE 能力 | 方案 A | 方案 B | 方案 C |
|---|---|---|---|
| IaC / Terraform | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 容器化运维 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Kubernetes | ❌ | ❌ | ⭐⭐⭐ |
| AWS 生态经验 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 成本控制 | ⭐⭐⭐ | ⭐⭐ | ⭐ |

### 3.5 推荐方案

**推荐方案 A（EC2 t3.small + Terraform）**，理由：

1. 月费仅 $17，适合个人项目长期维护
2. Terraform 管理 EC2 / VPC / S3 / IAM / CloudFront，足以展示 IaC 能力
3. 现有 docker-compose 架构无需大改，迁移成本低
4. 可观测性（Prometheus/Grafana）在单机上即可完整部署
5. 需要展示 K8s 时，可短期开 EKS 集群录屏截图后关闭，无需持续付费

---

## 4. 任务系统改造方案对比

### 4.1 现有方案：Celery + Redis

```
API ──► Redis(Broker) ──► Celery Worker ──► 执行任务（LLM/DB）
Beat ──► Redis ──► Celery Worker（定时：每5分钟 poll/match）
```

**优点：** 已完整运行，本地调试方便，支持任务重试/优先级队列
**缺点：** Worker / Beat / Redis 三个容器 24/7 占用内存，即使无任务也在运行

### 4.2 替代方案：Lambda + SQS + EventBridge

```
API ──► SQS ──► Lambda ──► 执行任务（LLM/DB）
EventBridge Scheduler ──► Lambda（替代 Celery Beat 定时触发）
```

**优点：** 按调用付费，低流量下近乎免费；无需维护长驻容器

**缺点：** 需重构所有 `@celery_app.task` 装饰器；本地调试需 AWS SAM / LocalStack

### 4.3 费用对比（<10 用户）

| 服务 | Celery + Redis | Lambda + SQS + EventBridge |
|---|---|---|
| 计算 | 含在 EC2 内（共享内存） | Lambda 调用 ~1万次/月 → **$0** |
| 消息队列 | Redis 容器（$0） | SQS ~1万消息/月 → **$0** |
| 定时调度 | Celery Beat 容器 | EventBridge Scheduler → **$0** |
| 间接节省 | — | EC2 可降至 t3.micro，省 $7/月 |

### 4.4 迁移约束

| 约束 | 说明 |
|---|---|
| Lambda 15 分钟超时 | LLM 单任务调用一般 5-30 秒，单条 SQS 消息触发单个 Lambda 可规避 |
| Redis 缓存依赖 | 项目使用 fastapi-cache2[redis]，去掉 Redis 需同步重构缓存层 |
| 批量任务拆分 | 原 Celery 任务若为批量处理多条记录，需拆分为单条事件驱动 |
| 本地开发复杂度 | 需引入 LocalStack 或 AWS SAM 模拟本地环境 |

### 4.5 推荐

**短期：保留 Celery + Redis**，优先完成可观测性建设。

**进阶（可选）：** 完成 AWS 迁移后，将任务系统改造为 Lambda + SQS，作为 Serverless 能力展示，并记录迁移过程作为技术博客素材。

---

## 5. 各方案对 SRE 目标的贡献度

| SRE 能力维度 | VPS + Prometheus | EC2 + Terraform | ECS Fargate | EKS | +Lambda/SQS |
|---|---|---|---|---|---|
| 可观测性 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| IaC | ❌ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 容器化 | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Serverless | ❌ | ❌ | ❌ | ❌ | ⭐⭐⭐ |
| Kubernetes | ❌ | ❌ | ❌ | ⭐⭐⭐ | ❌ |
| 成本优化 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ |
| **综合性价比** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ |

> **结论：** "VPS + Prometheus" 和 "EC2 + Terraform" 是当前阶段性价比最高的两步，能覆盖 SRE JD 中最核心的可观测性与 IaC 能力。

---

## 6. 可观测性专项规划

### 6.1 Prometheus 指标采集

在 FastAPI 中集成 `prometheus-fastapi-instrumentator`：

```python
# backend/app/main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

核心指标：
- `http_requests_total` — 请求总数（按状态码/路径分组）
- `http_request_duration_seconds` — 请求延迟（P50 / P95 / P99）
- Celery 任务队列深度（自定义 Gauge）
- Redis 内存使用率（redis-exporter）

### 6.2 Grafana Dashboard 设计要点

建议包含以下面板：

| 面板 | 指标来源 | 说明 |
|---|---|---|
| API 请求速率 | `rate(http_requests_total[5m])` | 按路径分组 |
| API P95 延迟 | `histogram_quantile(0.95, ...)` | 核心 SLI |
| 错误率 | 5xx 占总请求比例 | 核心 SLI |
| Celery 队列深度 | 自定义指标 | Worker 积压程度 |
| Redis 内存 | redis-exporter | 超 80% 触发告警 |
| 系统资源 | node-exporter | CPU / Mem / Disk |

### 6.3 Alertmanager 告警规则（核心 3 条）

```yaml
# prometheus/alert_rules.yml
groups:
  - name: jobpilot_slo
    rules:
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        annotations:
          summary: "API P95 latency > 2s"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "Error rate > 5%"

      - alert: HighRedisMemory
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.8
        for: 10m
        annotations:
          summary: "Redis memory usage > 80%"
```

### 6.4 SLO / SLI 定义与 Error Budget

| 指标 | SLI 定义 | SLO 目标 |
|---|---|---|
| 可用性 | 非 5xx 请求占总请求比例 | 99.5% / 月 |
| 延迟 | P95 响应时间 < 2s 的请求比例 | 95% |
| 任务成功率 | Celery 任务成功占总执行比例 | 98% |

**Error Budget 计算（可用性 SLO 99.5%）：**

```
月允许停机时间 = 30天 × 24h × 60min × (1 - 0.995) = 216 分钟/月
当前消耗：通过 Grafana Error Budget 面板实时追踪
```

---

## 7. 实施路线图

### 阶段 1：可观测性（当前 VPS，最高优先级）

- [ ] 在 FastAPI 中集成 `prometheus-fastapi-instrumentator`
- [ ] 在 docker-compose 中添加 Prometheus / Grafana / Alertmanager 服务
- [ ] 配置 Grafana Dashboard（API 延迟 / 错误率 / Celery 队列）
- [ ] 定义并文档化 SLO / SLI / Error Budget
- [ ] 编写 Runbook（告警触发时的处理流程）

### 阶段 2：迁移 AWS + Terraform IaC

- [ ] 新建 AWS 账号，配置 IAM / VPC / Security Group
- [ ] 编写 Terraform 模块：EC2 / S3 / CloudFront / Route53
- [ ] 迁移 CI/CD：GitHub Actions → 推送镜像到 ECR → 部署到 EC2
- [ ] 验证 Prometheus / Grafana 在 AWS 环境正常运行

### 阶段 3：Serverless 任务系统（可选进阶）

- [ ] 将 Celery 任务改写为 Lambda handler 函数
- [ ] 配置 SQS 队列（DLQ 处理失败任务）
- [ ] 用 EventBridge Scheduler 替代 Celery Beat 定时任务
- [ ] 重构缓存层（去除 Redis 或保留仅作缓存用途）
- [ ] 在 Terraform 中管理 Lambda / SQS / EventBridge 资源

### 阶段 4：K8s 能力展示（可选进阶）

- [ ] 编写 Kubernetes Deployment / Service / ConfigMap / Secret
- [ ] 配置 HPA（基于 CPU 或自定义指标）
- [ ] 在 EKS 上部署并验证（可短期运行后关闭以控制成本）
- [ ] 将 Kubernetes 配置纳入 Terraform 管理

---

## 8. 简历描述参考

### 最小版（完成阶段 1 后可用）

> Designed and operated a full-stack job aggregation platform with SRE practices: implemented observability stack (Prometheus/Grafana/Alertmanager), defined SLOs with error budget tracking, and maintained CI/CD pipelines with zero-downtime deployments on Docker/Nginx.

### 完整版（完成阶段 1-3 后可用）

> Built and operated a cloud-native job aggregation platform with full SRE lifecycle ownership: infrastructure-as-code (Terraform on AWS), containerization (Docker), CI/CD automation (GitHub Actions + ECR), observability stack (Prometheus/Grafana/Alertmanager), SLO definitions with error budget tracking, and serverless event-driven task processing (Lambda + SQS + EventBridge).
