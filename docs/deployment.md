# Hostinger VPS + GHCR + 统一 Nginx 网关部署方案

## 1. 目标与范围

本方案用于 JobPilot 生产部署，技术边界如下：
- Hostinger VPS（已启用 Docker Manager）
- GitHub Actions 负责构建与发布镜像
- GHCR（GitHub Container Registry）作为镜像仓库
- 一套共享 Nginx 作为统一反向代理网关（同时服务其他项目）
- 后端 API、Celery Worker、Redis 均容器化
- 数据库使用 Supabase PostgreSQL（托管，生产环境使用 Session Pooler）

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
- Supabase PostgreSQL，强制 SSL，生产环境使用 Session Pooler。

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
- `DATABASE_URL=<Supabase Session Pooler 连接串，含 ssl=require>`
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
- Supabase 生产环境使用 Session pooler 连接串。
- 对 `asyncpg` + Supabase pooler，建议附带 `prepared_statement_cache_size=0`，避免 pgbouncer prepared statement 问题。

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

### 11.4 Grafana Dashboard 面板

预置 Dashboard（`deploy/grafana/dashboards/jobpilot.json`）包含：

| 面板 | 指标 | 告警阈值颜色 |
|---|---|---|
| API 请求速率 | `rate(http_requests_total[5m])` | — |
| API P95 延迟 | `histogram_quantile(0.95, ...)` | 黄 > 1s / 红 > 2s |
| HTTP 5xx 错误率 | 5xx 占总请求比 | 黄 > 1% / 红 > 5% |
| Redis 内存使用率 | `redis_memory_used_bytes / redis_memory_max_bytes` | 黄 > 60% / 红 > 80% |

### 11.5 告警规则（`deploy/prometheus/alert_rules.yml`）

| 规则 | 触发条件 | 持续时间 | 严重级别 |
|---|---|---|---|
| `HighAPILatency` | P95 延迟 > 2s | 5 分钟 | warning |
| `HighErrorRate` | 5xx 错误率 > 5% | 5 分钟 | critical |
| `HighRedisMemory` | Redis 内存 > 80% | 10 分钟 | warning |

> 告警通过 Grafana 内置 SMTP 发送邮件。在 Grafana UI → Alerting → Contact points 中配置收件人。

### 11.6 SLO 定义

| 指标 | SLI | SLO 目标 |
|---|---|---|
| 可用性 | 非 5xx 请求占比 | 99.5% / 月（月允许故障 216 分钟） |
| 延迟 | P95 < 2s 的请求比例 | 95% |
| 任务成功率 | Celery 任务成功占比 | 98% |

---

## 12. 首次部署操作手册

首次部署按以下顺序执行，后续更新只需触发 CI/CD，无需重复。

### 12.1 前置条件

- VPS 已开通（本项目使用 Hostinger）
- 域名 `freeclaw.cloud` 已购买
- DNS 已将以下子域名 A 记录指向 VPS IP：
  - `app.freeclaw.cloud`
  - `api.freeclaw.cloud`

验证 DNS 是否生效（解析到正确 IP 才能继续）：

```bash
dig app.freeclaw.cloud +short
dig api.freeclaw.cloud +short
```

---

### 12.2 VPS 环境初始化

SSH 登录 VPS 后执行：

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 安装 Docker Compose 插件
apt install -y docker-compose-plugin

# 3. 安装 Nginx 和 Certbot
apt update
apt install -y nginx certbot python3-certbot-nginx

# 4. 开放防火墙端口（仅开放 22/80/443）
ufw allow 22
ufw allow 80
ufw allow 443
ufw enable
```

---

### 12.3 申请 SSL 证书

DNS 生效后执行（必须在 DNS 生效之后，否则 Let's Encrypt 域名验证失败）：

```bash
certbot --nginx -d app.freeclaw.cloud -d api.freeclaw.cloud
```

过程中：
- 输入邮箱（用于证书到期提醒）
- 选择 `2`（自动将 HTTP 重定向到 HTTPS）

验证自动续期：

```bash
certbot renew --dry-run
```

证书路径（供 Nginx 配置引用）：
```
/etc/letsencrypt/live/freeclaw.cloud/fullchain.pem
/etc/letsencrypt/live/freeclaw.cloud/privkey.pem
```

---

### 12.4 配置 GitHub Actions

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 中添加：

**Secrets（Settings → Secrets and variables → Actions → Secrets）：**

| 名称 | 说明 |
|---|---|
| `GHCR_USERNAME` | GitHub 用户名，用于登录 `ghcr.io` |
| `GHCR_TOKEN` | GitHub PAT，需勾选 `write:packages` + `read:packages` |
| `VPS_HOST` | VPS IP 地址 |
| `VPS_USER` | SSH 用户名（通常为 `root`） |
| `VPS_SSH_KEY` | SSH 私钥完整内容（含 `-----BEGIN...` 头尾） |
| `VPS_PORT` | SSH 端口（非 22 才填，否则不创建此 Secret） |

**Variables（Settings → Secrets and variables → Actions → Variables）：**

| 名称 | 值 | 说明 |
|---|---|---|
| `VITE_API_BASE_URL` | `https://api.freeclaw.cloud` | 前端构建时注入，非敏感，放 Variables 而非 Secrets |

> 说明：后端运行时业务变量（`DATABASE_URL`、`OPENAI_API_KEY` 等）不经过 GitHub Secrets，直接存放在 VPS 的 `backend.env` 文件中，首次部署时由 workflow 自动从模板生成后手动填写。

GHCR_TOKEN 生成路径：GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token，勾选 `write:packages`。

---

### 12.5 触发第一次部署（预期会失败一次）

在 GitHub Actions → Deploy Production → **Run workflow** 手动触发。

**预期结果**：在 `Deploy on VPS` 步骤失败，输出：

```
Missing .../backend.env. Template created, please fill secrets and rerun.
```

这是正常行为 — workflow 已将所有配置文件同步到 VPS，并自动从模板创建了 `backend.env` 和 `monitoring.env`。

---

### 12.6 SSH 进 VPS 填写配置文件

```bash
# 填写后端业务配置
nano /opt/jobpilot/deploy/env/backend.env
```

必填项：

| 变量 | 说明 |
|---|---|
| `SECRET_KEY` | 强随机字符串，可用 `openssl rand -hex 32` 生成 |
| `DATABASE_URL` | Supabase Session Pooler 连接串（含 `ssl=require&prepared_statement_cache_size=0`） |

推荐格式：

```bash
DATABASE_URL=postgresql+asyncpg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?ssl=require&prepared_statement_cache_size=0
```

说明：
- 不要在 VPS 生产环境使用 `db.<project-ref>.supabase.co:5432` 直连地址。
- 这类直连地址在部分仅 IPv4 的主机环境会解析到不可达地址，部署时常见报错为 `OSError: [Errno 101] Network is unreachable`。
- Supabase Dashboard 中请复制 `Connection string -> URI -> Session pooler` 版本。
| `OPENAI_API_KEY` | OpenAI API Key |
| `CORS_ORIGINS` | 保持 `["https://app.freeclaw.cloud"]` |

```bash
# 填写监控配置
nano /opt/jobpilot/deploy/env/monitoring.env
```

必填项：

| 变量 | 说明 |
|---|---|
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana 登录密码（自定义，勿用默认） |
| `GF_SMTP_USER` | 发件邮箱（Gmail 推荐） |
| `GF_SMTP_PASSWORD` | Gmail App Password（非登录密码，需在 Google 账号开启两步验证后生成） |
| `GF_SMTP_FROM_ADDRESS` | 同上发件邮箱 |

---

### 12.7 激活 Nginx 配置（首次一次性操作）

```bash
# 链接 JobPilot Nginx 配置到 sites-enabled
ln -s /opt/jobpilot/deploy/nginx/jobpilot.conf /etc/nginx/sites-enabled/jobpilot

# 验证语法
nginx -t

# 重载
systemctl reload nginx
```

> 后续每次 CI/CD 部署会自动同步最新的 `jobpilot.conf` 到 `/opt/jobpilot/deploy/nginx/`，但 symlink 只需创建一次，Nginx 会实时读取最新内容。

---

### 12.8 重新触发部署

再次 **Run workflow** — 这次应全程成功。

成功后验证：

```bash
# 确认所有容器运行正常
docker compose -f /opt/jobpilot/docker-compose.prod.yml ps

# 验证 API
curl https://api.freeclaw.cloud/health

# 验证 FastAPI 指标端点
curl http://127.0.0.1:18000/metrics | head -20
```

访问：
- 前端：`https://app.freeclaw.cloud`
- Grafana：`https://api.freeclaw.cloud/grafana`（用 `monitoring.env` 中的密码登录）

---

### 12.9 Grafana 邮件告警配置

登录 Grafana → **Alerting → Contact points → Add contact point**：
- Type: Email
- Addresses: 填写告警收件人邮箱
- 点击 **Test** 验证邮件发送正常后保存

---

### 12.10 部署后一次性补全操作

**配置 Docker 日志大小限制**

默认容器日志无上限，长期运行会写满磁盘。在 VPS 执行一次：

```bash
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker
```

**导出 Grafana 告警规则备份**

Dashboard 通过 provisioning 文件自动恢复，但在 Grafana UI 中手动创建的告警规则存储在 `grafana-data` volume 中，volume 误删后会丢失。配置好告警规则后从 Grafana UI 导出 JSON 并提交到仓库：

Grafana → Alerting → Alert rules → Export

---

### 12.11 验收清单

**基础部署：**
- CI 能构建并推送版本化镜像到 GHCR
- VPS 可用只读凭据拉取私有镜像
- Nginx `app/api` 路由正确，HTTPS 正常
- Worker 可消费 Redis 队列任务
- Supabase SSL 连接稳定
- Migration 流程可重复执行且无并发冲突
- 已验证至少一次镜像回滚

**可观测性：**
- `https://api.freeclaw.cloud/health` 返回 200
- `http://127.0.0.1:18000/metrics` 有 Prometheus 格式输出
- Grafana 可通过 `https://api.freeclaw.cloud/grafana` 访问
- Grafana Dashboard 4 个面板有实时数据
- 邮件告警 Test 发送成功

---

## 13. 回滚方案

应用回滚：
1. 将 compose 镜像 tag 回退到上一个稳定 `git-sha`。
2. `docker compose pull`
3. `docker compose up -d`
4. 验证 API 与 Worker 状态。

数据回滚：
- 优先前向修复。
- 严重故障按 Supabase 备份策略恢复。

---

## 14. 日常运维手册

### 13.1 日常（有告警时处理）

- 查看告警邮件，响应 `HighAPILatency` / `HighErrorRate` / `HighRedisMemory`
- 登录 `https://api.freeclaw.cloud/grafana` 巡检 Dashboard 趋势，发现阈值外异常

### 13.2 每月定期操作

**磁盘清理**（每次部署堆积旧镜像，长期不清理会撑满磁盘）

```bash
docker system prune -f
df -h
du -sh /var/lib/docker
```

**GHCR 旧镜像清理**

GitHub → Packages → jobpilot → 手动删除旧 `git-sha` 版本，或在 Package Settings 中配置自动清理策略。

**OS 安全补丁**

```bash
apt update && apt upgrade -y
```

**验证 SSL 证书状态**

```bash
certbot certificates
# 确认 VALID 且剩余天数 > 30，certbot systemd timer 会自动续期
```

### 13.3 需持续关注的外部限制

**Supabase 免费计划**

超过 **7 天无活跃请求**数据库会自动暂停，恢复需登录 Supabase Dashboard 手动点击 Restore。低流量阶段需确保有定期访问，或升级付费计划。

**GitHub Actions 额度**

私有仓库每月 2000 分钟免费，按现有 workflow 约 5 分钟/次，正常使用不会超额。公开仓库无限制。

## 15. 已落地文件清单

- 后端镜像构建：`backend/Dockerfile`
- 后端镜像构建忽略规则：`backend/.dockerignore`
- 生产编排：`docker-compose.prod.yml`
- VPS 部署脚本：`deploy/deploy-prod.sh`
- 后端环境变量模板：`deploy/env/backend.env.example`
- Nginx 配置模板：`deploy/nginx/jobpilot.conf`
- 自动发布流程：`.github/workflows/deploy.yml`
