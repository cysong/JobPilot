# Hostinger VPS + GHCR + 统一 Nginx 网关部署方案

## 1. 目标与范围

本方案用于 JobPilot 生产部署，技术边界如下：
- Hostinger VPS（已启用 Docker Manager）
- GitHub Actions 负责构建与发布镜像
- GHCR（GitHub Container Registry）作为镜像仓库
- 一套共享 Nginx 作为统一反向代理网关（同时服务其他项目）
- 后端 API、Celery Worker、Redis 均容器化
- 数据库使用 Supabase PostgreSQL（托管）

优先级：低成本优先，同时保证基础稳定性与可回滚。

---

## 1.1 已确认参数

- 根域名：`freeclaw.cloud`
- 前端域名：`app.freeclaw.cloud`
- API 域名：`api.freeclaw.cloud`
- 前端部署方式：Nginx 静态托管
- 定时任务：启用 `Celery Beat`
- 发布策略：合并到 `main` 后自动发布

---

## 2. 目标架构

- 入口层
  - VPS 上已有 Nginx 统一接入，负责 TLS 终止与反向代理。
- 前端
  - CI 构建静态文件，部署到 Nginx 静态目录（如 `/var/www/jobpilot`），由 `app.freeclaw.cloud` 访问。
- 后端
  - `jobpilot-api`：FastAPI 服务容器。
  - `jobpilot-worker`：Celery worker 容器。
  - `jobpilot-beat`：Celery Beat 定时任务容器（已启用）。
- 缓存/队列
  - `redis:7-alpine` 官方镜像，仅内网可访问。
- 数据库
  - Supabase PostgreSQL，强制 SSL。

网络原则：
- 对公网只开放 Nginx 的 `80/443`。
- API/Worker/Redis 仅在 Docker 内网通信，不直接暴露公网端口。

---

## 3. 域名与路由

推荐使用子域名：
- `app.freeclaw.cloud` -> 前端
- `api.freeclaw.cloud` -> FastAPI

说明：
- 该方式对 CORS、Cookie、WebSocket 管理最清晰。
- 与其他项目共享同一 Nginx 时，隔离度更高。

---

## 4. 生产环境变量

后端必需：
- `APP_ENV=production`
- `SECRET_KEY=<强随机字符串>`
- `DATABASE_URL=<Supabase 连接串，含 sslmode=require>`
- `REDIS_URL=redis://jobpilot-redis:6379/0`
- `CELERY_BROKER_URL=redis://jobpilot-redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://jobpilot-redis:6379/1`
- `OPENAI_API_KEY=<secret>`
- `CORS_ORIGINS=["https://app.freeclaw.cloud"]`
- `CORS_ALLOW_CREDENTIALS=true`

建议增加：
- `LOG_LEVEL=INFO`
- `WORKER_CONCURRENCY=<n>`
- `SENTRY_DSN=<可选>`

---

## 5. 镜像与版本策略

镜像命名：
- `ghcr.io/<org_or_user>/jobpilot:<git-sha>`

运行方式（同镜像，不同命令）：
- `jobpilot-api`：启动 FastAPI
- `jobpilot-worker`：启动 Celery Worker
- `jobpilot-beat`：启动 Celery Beat

策略：
- 生产环境只部署不可变 tag（`git-sha`）。
- `main/latest` 仅用于测试，不作为生产回滚基线。

---

## 6. GitHub Actions 发布流程

发布流水线：
1. 执行 lint/test。
2. 构建单个应用镜像。
3. 构建前端并上传 GitHub Artifact。
4. 推送后端镜像到 GHCR。
5. VPS 自动拉取指定 tag，并通过脚本从 GitHub Artifact 拉取前端静态文件后滚动更新。

必需 Secrets：
- `GHCR_USERNAME`
- `GHCR_TOKEN`
- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`

发布动作：
1. 合并到 `main`。
2. 产出 `git-sha` 后端镜像。
3. 产出前端构建 Artifact（`frontend-dist`）。
4. VPS 更新 compose 中镜像 tag，并下载前端 Artifact 到 Nginx 静态目录。
5. 执行 migration、`pull + up -d`、健康检查。

---

## 7. 运行时编排（Docker Compose）

建议服务：
- `jobpilot-api`
- `jobpilot-worker`
- `jobpilot-redis`
- `jobpilot-beat`

关键要求：
- `restart: unless-stopped`
- API、Redis 配置 `healthcheck`
- Redis 不映射宿主机公网端口
- API、Worker、Beat 使用同一镜像，不同启动命令

---

## 8. Nginx 网关要求

Nginx 需要满足：
- HTTP 自动跳转 HTTPS
- `api` 子域反代到 `jobpilot-api:8000`
- `app` 子域托管前端静态文件
- WebSocket 必需头：
  - `Upgrade`
  - `Connection "upgrade"`
- 上传与超时策略：
  - `client_max_body_size`
  - `proxy_read_timeout`

共享网关注意事项：
- JobPilot 使用独立 `server` 配置，不修改全局默认行为。
- 避免影响同机其他项目的路由与超时策略。

---

## 9. 数据库与迁移策略

上线顺序：
1. 拉取新镜像。
2. 执行 Alembic migration（一次且串行）。
3. 再启动/重启 API 与 Worker。

约束：
- 禁止多实例同时执行 migration。
- Supabase 优先使用 pooler 连接串（并发更稳）。

---

## 10. 安全基线

- 防火墙仅开放 `22/80/443`
- Secrets 仅放环境变量或密钥系统，禁止入库
- GHCR Token 使用最小权限
- Redis/API 不直接暴露公网
- VPS 开启系统安全更新

---

## 11. 可观测性栈（Prometheus + Grafana）

### 11.1 架构概览

```
FastAPI /metrics ──┐
redis-exporter     ├──► Prometheus(9090) ──► Grafana(3000) ──► Nginx /grafana
cAdvisor           ┘                              │
                                                  └──► Email Alert (SMTP)
```

监控服务全部运行在 `jobpilot-internal` Docker 网络内，不直接暴露公网端口。
Grafana 通过 Nginx 反代对外开放：`https://api.freeclaw.cloud/grafana`

### 11.2 容器清单（新增 4 个）

| 容器 | 镜像 | 端口（宿主机） | 用途 |
|---|---|---|---|
| `jobpilot-prometheus` | `prom/prometheus:v2.51.2` | 无 | 指标采集与存储（保留 15 天） |
| `jobpilot-grafana` | `grafana/grafana:10.4.2` | `127.0.0.1:13000` | 可视化 + 邮件告警 |
| `jobpilot-redis-exporter` | `oliver006/redis_exporter:v1.58.0` | 无 | 将 Redis 指标转为 Prometheus 格式 |
| `jobpilot-cadvisor` | `gcr.io/cadvisor/cadvisor:v0.49.1` | 无 | 容器 CPU/内存/网络资源 |

### 11.3 文件结构

```
deploy/
  prometheus/
    prometheus.yml          ← 抓取目标配置（api / redis-exporter / cadvisor）
    alert_rules.yml         ← 3 条核心告警规则
  grafana/
    provisioning/
      datasources/
        prometheus.yml      ← 自动注册 Prometheus 数据源
      dashboards/
        dashboard.yml       ← 自动加载 Dashboard 目录
    dashboards/
      jobpilot.json         ← 预置 4 面板 Dashboard
  env/
    monitoring.env.example  ← Grafana admin 密码 + SMTP 配置模板
    monitoring.env          ← 实际配置（不入库，首次部署手动创建）
```

### 11.4 首次部署步骤

1. 在 VPS 上复制环境变量模板并填写：
   ```bash
   cp /opt/jobpilot/deploy/env/monitoring.env.example \
      /opt/jobpilot/deploy/env/monitoring.env
   # 编辑 monitoring.env，填入强密码和 SMTP 配置
   ```

2. 正常触发 CI/CD 部署（`deploy-prod.sh` 已自动启动监控服务）。

3. 验证：
   ```bash
   # FastAPI 指标端点
   curl http://127.0.0.1:18000/metrics | head -20

   # Prometheus 是否抓到目标
   curl http://127.0.0.1:9090/api/v1/targets  # 从容器内访问，或临时端口映射
   ```

4. 访问 Grafana：`https://api.freeclaw.cloud/grafana`，用 `monitoring.env` 中的 admin 密码登录。

### 11.5 Grafana Dashboard 面板

预置 Dashboard（`deploy/grafana/dashboards/jobpilot.json`）包含：

| 面板 | 指标 | 告警阈值颜色 |
|---|---|---|
| API 请求速率 | `rate(http_requests_total[5m])` | — |
| API P95 延迟 | `histogram_quantile(0.95, ...)` | 黄 > 1s / 红 > 2s |
| HTTP 5xx 错误率 | 5xx 占总请求比 | 黄 > 1% / 红 > 5% |
| Redis 内存使用率 | `redis_memory_used_bytes / redis_memory_max_bytes` | 黄 > 60% / 红 > 80% |

### 11.6 告警规则（`deploy/prometheus/alert_rules.yml`）

| 规则 | 触发条件 | 持续时间 | 严重级别 |
|---|---|---|---|
| `HighAPILatency` | P95 延迟 > 2s | 5 分钟 | warning |
| `HighErrorRate` | 5xx 错误率 > 5% | 5 分钟 | critical |
| `HighRedisMemory` | Redis 内存 > 80% | 10 分钟 | warning |

> 告警通过 Grafana 内置 SMTP 发送邮件。在 Grafana UI → Alerting → Contact points 中配置收件人。

### 11.7 SLO 定义

| 指标 | SLI | SLO 目标 |
|---|---|---|
| 可用性 | 非 5xx 请求占比 | 99.5% / 月（月允许故障 216 分钟） |
| 延迟 | P95 < 2s 的请求比例 | 95% |
| 任务成功率 | Celery 任务成功占比 | 98% |

---

## 12. 回滚方案

应用回滚：
1. 将 compose 镜像 tag 回退到上一个稳定 `git-sha`。
2. `docker compose pull`
3. `docker compose up -d`
4. 验证 API 与 Worker 状态。

数据回滚：
- 优先前向修复。
- 严重故障按 Supabase 备份策略恢复。

---

## 13. 验收清单

- CI 能构建并推送版本化镜像到 GHCR
- VPS 可用只读凭据拉取私有镜像
- Nginx `app/api` 路由正确
- WebSocket 可通过 Nginx 正常连接
- Worker 可消费 Redis 队列任务
- Supabase SSL 连接稳定
- Migration 流程可重复执行且无并发冲突
- 已验证至少一次镜像回滚

---

## 14. 已落地测试文件

- 后端镜像构建：`backend/Dockerfile`
- 后端镜像构建忽略规则：`backend/.dockerignore`
- 生产编排：`docker-compose.prod.yml`
- VPS 部署脚本：`deploy/deploy-prod.sh`
- 后端环境变量模板：`deploy/env/backend.env.example`
- Nginx 配置模板：`deploy/nginx/jobpilot.conf`
- 自动发布流程：`.github/workflows/deploy.yml`

---

## 15. GitHub Secrets 清单

以下是当前 `.github/workflows/deploy.yml` 实际读取的 Secrets：

必需：
- `GHCR_USERNAME`：用于登录 `ghcr.io`
- `GHCR_TOKEN`：用于推送/拉取 GHCR 镜像
- `VPS_HOST`：VPS 主机地址
- `VPS_USER`：VPS SSH 用户
- `VPS_SSH_KEY`：VPS SSH 私钥（建议专用 deploy key）

可选：
- `VPS_PORT`：SSH 端口，未设置时默认 `22`

说明：
- 后端运行时业务变量（如 `DATABASE_URL`、`OPENAI_API_KEY`、`CORS_ORIGINS`）不从 GitHub Secrets 注入容器。
- 这些变量放在 VPS 文件：`/opt/jobpilot/deploy/env/backend.env`（首次部署会由模板自动生成）。
- 前端变量 `VITE_API_BASE_URL` 由 GitHub Repository Variable 注入前端构建流程。

---

## 16. GitHub Variables 清单

当前 workflow 需要的 Variables：
- `VITE_API_BASE_URL`：前端构建时使用，例如 `https://api.freeclaw.cloud`

说明：
- 此变量非敏感信息，建议放 Variables，不放 Secrets。
- workflow 在前端构建前会校验该变量，未配置会直接失败并提示。
