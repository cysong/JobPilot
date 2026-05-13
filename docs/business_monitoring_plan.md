# JobPilot 业务监控改造方案

## 1. 背景与目标

### 1.1 现状

项目已具备：

- ✅ Prometheus + Grafana + cAdvisor + redis-exporter 容器编排（[docker-compose.prod.yml](../docker-compose.prod.yml)）
- ✅ Prometheus scrape FastAPI `/metrics` 端点（[deploy/prometheus/prometheus.yml](../deploy/prometheus/prometheus.yml)）
- ✅ Grafana 自动 provisioning（datasource + dashboard）
- ✅ 基础设施层告警规则 3 条（[deploy/prometheus/alert_rules.yml](../deploy/prometheus/alert_rules.yml)）
- ✅ Celery 信号处理（retry / failure / success），但仅写日志（[backend/app/core/celery_app.py:81-143](../backend/app/core/celery_app.py)）
- ✅ FastAPI 全局异常 handler 3 个（[backend/app/main.py:73-117](../backend/app/main.py)）
- ✅ Resend 邮件 SDK 已集成（[backend/app/modules/auth/email_service.py](../backend/app/modules/auth/email_service.py)）
- ✅ LLM 调用统一走 `AgentGateway`，已有 latency / token / cost 日志（[backend/app/core/llm/gateway.py](../backend/app/core/llm/gateway.py)）

### 1.2 缺口

- ❌ 无业务维度指标（HTTP `/metrics` 只有 instrumentator 默认的请求计数与延迟）
- ❌ Celery / LLM / Resend / Job ingest 都没有 Prometheus counter，事件只落日志
- ❌ 无 Alertmanager，alert rules fire 之后无人接收
- ❌ Grafana 只有一张设施视角 dashboard，无业务视角、无 SLO/Error Budget

### 1.3 目标

- 覆盖 5 个核心业务面：API 错误、Celery 任务、LLM 调用、Resend 邮件、Job 入队
- 10 条告警规则（4 SLO + 3 异常模式 + 3 基础设施），按 severity 路由（critical 立即发 / warning 节流发）
- 3 张 Grafana dashboard：Overview / SLO / Business Detail
- 30d 滚动窗口 Error Budget 跟踪
- 邮件告警走 Gmail SMTP（复用 Grafana 已配置的 `GF_SMTP_*` 变量），与业务用的 Resend 完全隔离，避免任一条邮件链路挂掉时遮蔽另一条

---

## 2. 业务指标设计

### 2.1 指标清单（9 个）

| 指标名 | 类型 | 标签 | 用途 |
|---|---|---|---|
| `jobpilot_api_error_total` | Counter | `endpoint, code, exception_type` | 业务异常（JobPilotException + 5xx fallback） |
| `jobpilot_celery_task_total` | Counter | `task_name, event` | event ∈ {success, failure, retry} |
| `jobpilot_celery_task_duration_seconds` | Histogram | `task_name` | task 执行时长分布 |
| `jobpilot_celery_queue_length` | Gauge | `queue_name` | Redis 队列堆积（探针 task 周期写入） |
| `jobpilot_llm_call_total` | Counter | `agent_id, provider, model, outcome` | outcome ∈ {ok, ratelimit, timeout, auth_error, max_turns, error} |
| `jobpilot_llm_call_duration_seconds` | Histogram | `agent_id, provider, model` | LLM 延迟 |
| `jobpilot_llm_tokens_total` | Counter | `agent_id, provider, model, kind` | kind ∈ {input, output}，与成本挂钩 |
| `jobpilot_resend_email_total` | Counter | `kind, outcome` | kind ∈ {verification, password_reset}；outcome ∈ {ok, error} |
| `jobpilot_job_ingest_total` | Counter | `source, outcome` | source=manual_url；outcome ∈ {ok, error, timeout, bad_request, unavailable} |

### 2.2 单位与基数约定

- **时间单位统一 seconds**（Prometheus 标准约定）。Grafana 展示时选 unit `s`，自动按数值显示 ms/s/min
- **agent_id** 控制在 10 个枚举值以内，超过需移出 label
- **不打 user_id / request_id label**，高基数走日志，不走 metric
- **endpoint 用 FastAPI route pattern**（instrumentator 默认行为）

### 2.3 埋点位置

| 位置 | 改动 |
|---|---|
| [backend/app/main.py:82-117](../backend/app/main.py) | `jobpilot_exception_handler` + fallback handler 各加 `.inc()` |
| [backend/app/core/celery_app.py:81-143](../backend/app/core/celery_app.py) | 三个信号 + 新增 `task_prerun` / `task_postrun` 算 duration |
| [backend/app/core/llm/gateway.py:46-99](../backend/app/core/llm/gateway.py) | `_log_success` / `_log_error` 调用点旁加 metric；用现成的 `_classify_error` 当 outcome label |
| [backend/app/modules/auth/email_service.py:22-38](../backend/app/modules/auth/email_service.py) | `_send` try/except 包一层，记 outcome |
| [backend/app/modules/jobs/service.py:608](../backend/app/modules/jobs/service.py) | `enqueue_job_url` 4 个分支各打一次 metric |
| 新增 `backend/app/core/tasks_observability.py` | 周期性探针 task，每 60s 读 Redis 队列长度写 Gauge |

---

## 3. Alertmanager 部署

### 3.1 服务编排（docker-compose.prod.yml 新增 service）

```yaml
alertmanager:
  image: prom/alertmanager:v0.27.0
  container_name: jobpilot-alertmanager
  restart: unless-stopped
  volumes:
    - ./deploy/alertmanager:/etc/alertmanager:ro
    - alertmanager-data:/alertmanager
  command:
    - '--config.file=/etc/alertmanager/alertmanager.yml'
    - '--storage.path=/alertmanager'
  networks: [monitoring]
```

### 3.2 Prometheus 关联（prometheus.yml 新增）

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ["jobpilot-alertmanager:9093"]
```

### 3.3 路由配置（deploy/alertmanager/alertmanager.yml）

```yaml
route:
  receiver: resend-email
  group_by: [alertname, severity]
  group_wait: 30s          # warning/info: 等 30s 合并同组
  group_interval: 5m
  repeat_interval: 4h      # 未解决告警每 4h 重发
  routes:
    - matchers: [severity="critical"]
      receiver: resend-email
      group_wait: 0s        # critical: 立刻发
      repeat_interval: 1h   # 未解决每 1h 催
    - matchers: [severity="info"]
      receiver: "null"      # info 只显示在 Grafana，不发邮件

receivers:
  - name: "null"

  - name: gmail
    email_configs:
      - to: yansongc@gmail.com
        from: yansongc@gmail.com
        smarthost: smtp.gmail.com:587
        auth_username: yansongc@gmail.com
        auth_identity: yansongc@gmail.com
        auth_password_file: /etc/alertmanager/secrets/smtp_password
        require_tls: true
        send_resolved: true

inhibit_rules:
  # critical 触发时，同名 warning 不重复打扰
  - source_matchers: [severity="critical"]
    target_matchers: [severity="warning"]
    equal: [alertname]
```

### 3.4 环境变量

复用 [monitoring.env](../deploy/env/monitoring.env.example) 里已有的 `GF_SMTP_*`：
- `GF_SMTP_USER` / `GF_SMTP_FROM_ADDRESS` —— 都是 `yansongc@gmail.com`，已在 alertmanager.yml 里硬编码
- `GF_SMTP_PASSWORD` —— Gmail 应用专用密码（16 字符），alertmanager 容器 entrypoint 启动时写入 `/etc/alertmanager/secrets/smtp_password`，由 `auth_password_file` 读取，配置文件本身不含密钥
- **Resend 的 `RESEND_API_KEY` 保持只给业务代码用**（[email_service.py](../backend/app/modules/auth/email_service.py)），告警链路完全独立

---

## 4. 告警规则（12 条）

文件：[deploy/prometheus/alert_rules.yml](../deploy/prometheus/alert_rules.yml)

### 4.1 SLO 锚定（4 条）

```yaml
- alert: APIHighErrorRate
  expr: |
    sum(rate(http_requests_total{status=~"5.."}[5m]))
    / sum(rate(http_requests_total[5m])) > 0.05
  for: 5m
  labels: { severity: critical }

- alert: APISlowRequests
  # avg, not p95 — single-user low-traffic systems don't have enough samples for stable quantiles.
  expr: |
    sum(rate(http_request_duration_seconds_sum[10m]))
    / sum(rate(http_request_duration_seconds_count[10m])) > 1
  for: 10m
  labels: { severity: warning }

- alert: CeleryTaskFailureRate
  expr: |
    sum(rate(jobpilot_celery_task_total{event="failure"}[10m])) by (task_name)
    / sum(rate(jobpilot_celery_task_total{event=~"success|failure"}[10m])) by (task_name)
    > 0.1
  for: 10m
  labels: { severity: warning }

- alert: LLMCallFailureRate
  expr: |
    sum(rate(jobpilot_llm_call_total{outcome!="ok"}[10m])) by (agent_id)
    / sum(rate(jobpilot_llm_call_total[10m])) by (agent_id) > 0.2
  for: 10m
  labels: { severity: warning }
```

### 4.2 异常模式（3 条）

```yaml
- alert: CeleryRetryStorm
  expr: sum(rate(jobpilot_celery_task_total{event="retry"}[5m])) by (task_name) > 0.5
  for: 5m
  labels: { severity: warning }

- alert: CeleryQueueBacklog
  expr: jobpilot_celery_queue_length > 100
  for: 10m
  labels: { severity: warning }

- alert: ResendDeliveryFailure
  expr: |
    sum(rate(jobpilot_resend_email_total{outcome="error"}[10m]))
    / sum(rate(jobpilot_resend_email_total[10m])) > 0.1
  for: 5m
  labels: { severity: critical }
```

### 4.3 基础设施（3 条）

保留 HighRedisMemory（原有），新增 APIDown 与 PrometheusTargetDown。
原 HighAPILatency / HighErrorRate 与 SLO 区的 APIHighLatency / APIHighErrorRate 重复，已合并到 SLO 区。

```yaml
- alert: APIDown
  expr: up{job="jobpilot-api"} == 0
  for: 1m
  labels: { severity: critical }

- alert: PrometheusTargetDown
  expr: up == 0
  for: 5m
  labels: { severity: warning }
```

### 4.4 工程化约定

- 每条 alert 必须有 `severity` label（critical / warning / info）
- 每条 alert 必须有 `summary` + `description` annotation
- 每条 alert 必须有 `runbook_url` 指向 `docs/runbooks/<alert_name>.md`
- 表达式统一用 `rate(...[5m])` 或 `rate(...[10m])`

---

## 5. Grafana Dashboard

### 5.1 三张 Dashboard

| 文件 | 用途 |
|---|---|
| [jobpilot.json](../deploy/grafana/dashboards/jobpilot.json)（保留改造） | Overview：日常巡检 1 分钟看完 |
| `jobpilot-slo.json`（新建） | SLO & Error Budget：月度复盘、简历展示 |
| `jobpilot-business.json`（新建） | Business Detail：排查问题下钻 |

### 5.2 Overview Dashboard（追加 1 个 row）

在现有 4 个 panel 基础上补一个 "Business Health" row：

- Celery 任务速率（按 task 堆叠）：`sum(rate(jobpilot_celery_task_total[5m])) by (task_name, event)`
- Celery 失败率：`sum(rate(jobpilot_celery_task_total{event="failure"}[5m])) by (task_name) / sum(rate(jobpilot_celery_task_total{event=~"success|failure"}[5m])) by (task_name)`
- LLM 失败率：同上结构
- 当前 firing 告警数量 Stat（数据源 Alertmanager）

### 5.3 SLO Dashboard（新增）

| Panel | 表达式 | 类型 |
|---|---|---|
| API 可用性（30d 滚动） | `1 - (sum(increase(http_requests_total{status=~"5.."}[30d])) / sum(increase(http_requests_total[30d])))` | Stat，target 99.5% |
| Task 成功率（30d） | `sum(increase(jobpilot_celery_task_total{event="success"}[30d])) / sum(increase(jobpilot_celery_task_total{event=~"success\|failure"}[30d]))` | Stat，target 98% |
| LLM 成功率（30d） | `sum(increase(jobpilot_llm_call_total{outcome="ok"}[30d])) / sum(increase(jobpilot_llm_call_total[30d]))` | Stat，target 95% |
| Error Budget 剩余 | `1 - ((1 - availability) / 0.005)` | Gauge，max 100% |
| Error Budget 燃尽图 | 累计错误率 vs SLO 直线 | Time series |

### 5.4 Business Detail Dashboard（新增）

四个 row：

- **Celery**：task 速率（按 task 堆叠） / P95 时长（按 task）/ 队列堆积 / Retry rate
- **LLM**：调用速率（按 agent_id 堆叠）/ P95 延迟（按 model）/ Token 消耗趋势（按 model）/ 失败原因分布（按 outcome）
- **API 业务错误**：错误码 Top10 / 各 endpoint 错误率
- **Resend & Ingest**：邮件成功率 / Job 入队成功率

### 5.5 共用增强

- **Variables**：顶部 `$task_name`、`$agent_id`、`$endpoint` 下拉
- **Annotations**：把 GitHub Actions 部署成功事件打到时间轴
- **Alertmanager 数据源**：[provisioning/datasources](../deploy/grafana/provisioning/datasources/) 新增，用于显示 firing 状态

---

## 6. Runbook 模板

文件结构：`docs/runbooks/<alert_name>.md`，每个 alert 对应一份。模板：

```markdown
# <Alert Name>

**Severity**: critical | warning
**Trigger**: <PromQL 表达式简述>

## 影响
<用户能感知到什么？>

## 初步排查
1. 看 Grafana <link>
2. 查 logs：`docker logs jobpilot-api --tail 500 | grep ERROR`
3. ...

## 常见原因
- ...

## 缓解措施
- ...

## 升级
若 X 分钟未恢复，联系：...
```

需要写的 runbook：12 个（每条 alert 一个）。

---

## 7. 落地路线

按依赖顺序，每步可独立验收：

| Phase | 工作量 | 交付 | 验收方式 |
|---|---|---|---|
| **P1 业务指标埋点** | 半天 | `metrics.py` + 6 处 handler/调用改造 | `curl /metrics \| grep jobpilot_` 看到全部新指标 |
| **P2 告警规则补充** | 1h | 更新 `alert_rules.yml`（10 条规则合并版） | Prometheus UI Alerts 页面看到 10 条 inactive |
| **P3 Alertmanager 部署** | 半天 | docker-compose 加 service + `alertmanager.yml` | 制造 5xx → Resend 邮件到达 |
| **P4 SLO Dashboard** | 半天 | `jobpilot-slo.json` | Grafana 自动加载，三个 SLO Stat 数字合理 |
| **P5 Business Detail + Runbook** | 1 天 | `jobpilot-business.json` + 10 份 runbook | 简历级成品 |

**总计**：约 3 个工作日，可分散落地。

---

## 8. 不在本次范围

明确砍掉，避免范围蔓延：

- ❌ 飞书 webhook 通知（单渠道邮件足够）
- ❌ Loki 日志聚合 + drilldown links
- ❌ 分布式 tracing（OpenTelemetry）
- ❌ 前端 Sentry / 错误监控
- ❌ Webhook 适配器方案（避免循环依赖）
- ❌ 短信 / 电话告警

留作未来扩展，但不影响本次 SLO 与告警闭环。
