# JobPilot Alert Runbooks

> 每条告警对应一节，告警邮件中的 `Runbook` 链接直接指向对应锚点。
> 告警规则：[deploy/prometheus/alert_rules.yml](../deploy/prometheus/alert_rules.yml)；SLO 定义：[slo.md](slo.md)。

**Last Updated:** 2026-11-06

---

## 0. 通用

### 入口

| 用途 | 地址 / 命令 |
|---|---|
| Grafana | `https://api.freeclaw.cloud/grafana`（JobPilot + Business Detail 两个 dashboard） |
| Admin 任务列表 / 分析 | `https://app.freeclaw.cloud/admin/tasks`、`/admin/tasks/chart` |
| VPS 部署目录 | `/opt/jobpilot` |

### 常用命令（在 VPS 上执行）

```bash
cd /opt/jobpilot
alias dc='docker compose -f docker-compose.prod.yml'

dc ps                                   # 容器状态 / 健康检查
dc logs --since 30m jobpilot-api        # API 日志
dc logs --since 30m jobpilot-worker     # Celery worker 日志
dc logs --since 30m jobpilot-beat       # Celery beat 日志
dc restart jobpilot-worker              # 重启单个服务
docker stats --no-stream                # 容器 CPU / 内存
curl -fsS http://127.0.0.1:18000/health # API 本机健康检查
dc exec jobpilot-redis redis-cli info memory
dc exec jobpilot-redis redis-cli llen celery
```

### 通用处理流程

1. **确认影响面**：是否真实用户受影响（看 Grafana 中排除 `/metrics` 后的请求量），是否只有一个 task / agent 出问题。
2. **找最近变更**：先看 `git log` 和 GitHub Actions 最近一次部署。如果告警是部署后立刻出现的，优先回滚（重新运行上一次成功的 deploy workflow）。
3. **止血优先于根因**：需要时先重启服务、暂停定时任务（`DISABLE_BEAT_TASKS=true`），再查根因。
4. **记录**：非误报的告警写入 [issues.md](issues.md)（问题 → 根因 → 解决 → 验证）。

---

## APIHighErrorRate

**含义：** 5 分钟内 HTTP 5xx 占比超过 5%，持续 5 分钟。**critical**

**影响：** 用户请求失败，直接消耗 API 可用性 Error Budget。

**排查：**
1. 在 Grafana 中按 `handler` 拆分 5xx，确认是哪个接口：
   ```promql
   sum by (handler) (rate(http_requests_total{status=~"5.."}[5m]))
   ```
2. 看业务异常分布：
   ```promql
   sum by (endpoint, exception_type) (rate(jobpilot_api_error_total[10m]))
   ```
3. 查看 `dc logs --since 15m jobpilot-api`，搜索 `Traceback` / `ERROR`。

**常见原因与处理：**

| 原因 | 特征 | 处理 |
|---|---|---|
| 数据库连接失败（Supabase pooler） | 日志出现 `asyncpg` / `ConnectionRefused` / `DuplicatePreparedStatementError` | 检查 Supabase 状态页；核对 `DATABASE_URL` 中的 pooler 参数；必要时 `dc restart jobpilot-api` |
| Redis 不可用 | `redis.exceptions.ConnectionError` | 见 [HighRedisMemory](#highredismemory)；`dc restart jobpilot-redis` |
| 新部署引入 bug | 部署后立刻出现，集中在某一个 handler | 回滚到上一个镜像 |
| 外部依赖 503（如 `/jobs/enqueue` 的 AWS Function URL） | `ServiceUnavailableError` | 确认上游状态，属于预期降级，记录即可 |

---

## APISlowRequests

**含义：** 10 分钟滚动平均请求耗时超过 1s，持续 10 分钟。**warning**

**影响：** 页面加载变慢，消耗 API 延迟 Error Budget。

**排查：**
1. 按 handler 找出慢接口：
   ```promql
   sum by (handler) (rate(http_request_duration_seconds_sum[10m]))
   / sum by (handler) (rate(http_request_duration_seconds_count[10m]))
   ```
2. `docker stats --no-stream`：看 API 容器 CPU 是否打满、是否接近内存上限。
3. 如果慢的是查询类接口，到 Supabase Dashboard → Query Performance 查看慢 SQL。

**常见原因与处理：**
- **数据库慢查询或 N+1：** 定位后加索引、收窄 SELECT（参考 2026-04 的 egress 优化）。
- **PDF 导出等重操作偶发变慢：** 低流量下一两个慢请求就能拉高平均值。如果只集中在导出接口，可以先记录，不必处理。
- **VPS 资源争用：** 确认 worker 或其他进程是否占满 CPU，必要时降低 `CELERY_WORKER_CONCURRENCY`。

---

## CeleryTaskFailureRate

**含义：** 某个 `task_name` 的失败率超过 10%（10 分钟窗口），持续 10 分钟。**warning**

**影响：** 职位分析、求职信生成等后台流程失败，消耗任务成功率 Error Budget。

**排查：**
1. 告警标签里的 `task_name` 就是出问题的任务。到 Admin → Tasks 页面查看失败任务的错误信息。
2. 查看 `dc logs --since 30m jobpilot-worker | grep -i -E 'error|exception'`。
3. 如果是 LLM 相关任务，同时检查是否有 [LLMCallFailureRate](#llmcallfailurerate) 告警。

**常见原因与处理：**
- **LLM Provider 故障：** 见 [LLMCallFailureRate](#llmcallfailurerate)。
- **输入数据异常（个别职位的 JD 格式异常）：** 失败集中在少数几条记录时，确认是数据问题后记录到 issues.md 并修复解析逻辑。
- **代码 bug（部署后出现）：** 回滚。
- **需要暂停定时任务止血：** 在 `deploy/env/backend.env` 中设置 `DISABLE_BEAT_TASKS=true`，然后执行 `dc up -d jobpilot-beat`。beat 只在启动时读取调度表，所以必须重建容器才会生效。

---

## LLMCallFailureRate

**含义：** 某个 `agent_id` 的 LLM 调用非 `ok` 比例超过 20%，持续 10 分钟。**warning**

**影响：** 职位分析、简历分析、求职信生成质量下降或失败。

**排查：**
```promql
sum by (agent_id, provider, model, outcome) (increase(jobpilot_llm_call_total{outcome!="ok"}[30m]))
```

| `outcome` | 含义 | 处理 |
|---|---|---|
| `ratelimit` | Provider 限流 | 降低 `CELERY_WORKER_CONCURRENCY`；检查账户额度与 tier；临时把该 agent 切到其他 provider |
| `timeout` | 调用超时 | 查看 Provider 状态页；内容过长时考虑截断输入 |
| `auth_error` | API Key 失效或余额不足 | 检查 OpenAI / OpenRouter 控制台的余额和 Key，更新 `backend.env` 后重启 worker |
| `max_turns` | Agent 超过最大轮次 | 查看 agent 配置（`backend/agent_configs/config/*.yaml`）和 prompt，属于逻辑问题 |
| `error` | 其他异常 | 查看 worker 日志中带 `provider` / `agent_id` 的异常详情 |

**切换 provider：** 修改 `backend/agent_configs/config/*.yaml` 中对应 agent 的 provider/model 配置并重新部署。

---

## CeleryRetryStorm

**含义：** 某个任务 5 分钟内重试速率超过 0.5 次/秒，持续 5 分钟。**warning**

**影响：** 通常是下游依赖（LLM、数据库、外部 API）持续故障，重试会放大负载和 LLM 费用。

**排查与处理：**
1. 找到告警中的 `task_name`，从 worker 日志确认重试的原因（异常类型）。
2. 下游明确故障时，先暂停定时任务止血（`DISABLE_BEAT_TASKS=true`，见上文），避免持续产生新任务。
3. 等下游恢复后再恢复定时任务。如果队列里已经积压了大量注定失败的任务，见 [CeleryQueueBacklog](#celeryqueuebacklog) 中的清理步骤。

---

## CeleryQueueBacklog

**含义：** `celery` 队列长度超过 100，持续 10 分钟。**warning**

**影响：** 后台处理延迟，用户提交的分析或生成任务迟迟没有结果。

**排查：**
1. `dc ps`：确认 `jobpilot-worker` 在运行。
2. `dc logs --since 15m jobpilot-worker`：确认 worker 在正常消费，而不是卡住或在不断重启。
3. 在 Grafana 中查看任务执行时长是否突然变长（`jobpilot_celery_task_duration_seconds`）。

**处理：**
- **worker 挂掉或卡死：** `dc restart jobpilot-worker`。
- **任务变慢（多为 LLM 延迟升高）：** 临时调高 `CELERY_WORKER_CONCURRENCY`（注意 LLM 限流），或者暂停定时任务让队列自然消化。
- **队列里全是注定失败的任务：** 确认可以丢弃后执行 `dc exec jobpilot-worker uv run celery -A app.core.celery_app purge -f`。⚠️ 这会丢弃所有待处理任务；`poll_unanalyzed_jobs` 会在下一轮重新拉取未分析的职位。

---

## ResendDeliveryFailure

**含义：** Resend 邮件发送失败率超过 10%（排除 `validation_error`），持续 5 分钟。**critical**

**影响：** 注册验证、找回密码、修改邮箱的邮件发不出去，用户无法完成这些流程。

**排查：**
```promql
sum by (kind, outcome) (increase(jobpilot_resend_email_total[1h]))
```
- `rate_limit`：触发 Resend 速率限制，检查是否有异常的批量发送（例如重发验证邮件被刷）。
- 其他：登录 Resend Dashboard 查看 Logs，检查 API Key、发信域名的 DNS（SPF / DKIM）验证状态和账户额度。

**处理：** 修复配置后更新 `deploy/env/backend.env` 中的 `RESEND_*`，然后 `dc up -d jobpilot-api`。

> 告警邮件本身走 Gmail SMTP，与 Resend 相互独立，所以这条告警在 Resend 故障时依然能送达。

---

## LLMQuotaPaused

**含义：** OpenRouter 额度用完（403 "Key limit exceeded" / 402 余额不足），或 key 剩余额度低于 `LLM_QUOTA_PAUSE_THRESHOLD_USD`（默认 $2），所有大模型工作已暂停。**critical**

**影响：** 申请生成、岗位分析、简历分析、匹配判定全部挂起；新提交的申请会创建但不执行。不消耗重试次数，不会把任务标为失败。

**排查：**
1. 管理后台 Dashboard 的 "LLM quota" 卡片：暂停原因、时间、key 剩余额度。
2. 或调用 `GET /api/v1/admin/llm/quota`。

**处理：**
- 在 OpenRouter 提高 key 额度或充值。`llm_quota_watch` 每 5 分钟检查一次，额度恢复后自动解除暂停并重新提交挂起的任务。
- 想立即恢复：后台卡片点 "Resume"（或 `POST /api/v1/admin/llm/quota/resume`）。
- 额度未恢复就手动恢复，下一次调用会再次触发暂停。

---

## MatchQueueStale

**含义：** 有新岗位的匹配排队超过 24 小时，持续 15 分钟（回填不计）。**warning**

**影响：** 新岗位迟迟没有档位，可能在判定前就过期。

**排查：**
1. `dc logs --since 30m jobpilot-worker | grep match_judge`：看 `judge_queued_matches_task` 是否在跑、有没有报错。
2. Grafana 匹配面板：`jobpilot_match_judge_total` 是否还在增长；`jobpilot_match_queue_depth` 是否持续上升。
3. 日志里 `limited_users` 非空：用户已用完当日调用上限（`MATCH_DAILY_LLM_LIMIT_PER_USER`）。
4. 大量 `failed_retryable`：多为 OpenRouter 限流、余额不足（402）或 key 失效。

**处理：**
- **worker / beat 不在运行：** `dc restart jobpilot-worker jobpilot-beat`。
- **每日上限用尽：** 等第二天自动继续；岗位多时可临时调高上限后重建 worker。
- **OpenRouter 余额或 key 问题：** 充值或更新 `deploy/env/backend.env` 中的 `OPENROUTER_API_KEY`，再重建 api / worker / beat。

---

## MatchFailedFinalRatio

**含义：** 最近 24 小时最终失败的判定超过 5%（判定数至少 20）。**warning**

**影响：** 这些岗位不会再判定，用户看不到结果。

**排查：**
1. 查失败原因：
   ```sql
   select left(error, 120) as error, count(*) from job_matches
   where status = 'failed_final' and judged_at > now() - interval '24 hours'
   group by 1 order by 2 desc;
   ```
2. `invalid output after retries`：模型输出结构异常，检查最近是否改过 prompt / schema / 模型。
3. `gateway error`：重试 3 次仍失败，多为 provider 持续故障。
4. `no candidate resumes`：判定前简历被删除或解绑，属正常情况。

**处理：** 修复原因后，把需要重判的行改回 `queued`（`attempts = 0, next_attempt_at = null`），下一轮会重新判定。

---

## MatchNoATier

**含义：** 最近 24 小时判定超过 20 次但没有一个 A 档，持续 1 小时。**warning**

**影响：** 推荐列表空了，可能是档位标准漂移。

**排查：**
1. 看档位分布：`jobpilot_match_tier_24h`，是否全部落到 B / C。
2. 最近是否修改了 `match_judge` prompt、`MATCH_JUDGE_MODEL` 或 `MATCH_JUDGE_PROMPT_VERSION`。
3. 抽查几条当天的 `tier_reason`，确认是不是岗位本身就不匹配（例如新绑定的简历岗位族不对）。

**处理：** prompt 或模型问题时回退到上一个版本，并在评估数据集上重跑对比后再上线。

---

## APIDown

**含义：** Prometheus 连续 1 分钟抓取不到 `jobpilot-api`。**critical**。触发后会抑制所有其他业务告警。

**影响：** 整站不可用。

**排查与处理：**
1. 从外部确认：`curl -fsS https://api.freeclaw.cloud/health`（或浏览器打开站点）。
2. 在 VPS 上执行 `dc ps`，看 `jobpilot-api` 的状态：
   - **`restarting` / `exited`：** `dc logs --tail 200 jobpilot-api` 查看启动报错。常见原因是 env 缺变量、迁移失败、依赖 Redis 不健康。
   - **`unhealthy`：** 执行 `curl -fsS http://127.0.0.1:18000/health`，看是否卡在数据库连接。
   - **`running` 且本机健康，但 Prometheus 抓不到：** 属于网络问题，检查 `jobpilot-internal` 网络和 Prometheus 容器。
3. 如果是部署引起的，回滚到上一次成功的镜像。
4. 如果整机不可达（SSH 也连不上），到 VPS 服务商控制台重启实例。

---

## PrometheusTargetDown

**含义：** 某个抓取目标（`jobpilot-worker` / `redis` / `cadvisor` 等）连续 5 分钟不可达。**warning**

**影响：** 该目标的指标缺失，相关告警会失效。如果目标是 `jobpilot-worker`，后台任务很可能也停了。

**处理：**
1. 告警标签中的 `job` / `instance` 指明是哪个目标。执行 `dc ps` 查看对应容器状态。
2. 用 `dc logs --tail 100 <container>` 查看日志，然后 `dc restart <container>`。
3. 如果是 `jobpilot-worker` 的 metrics 端口（9101）不通但 worker 本身在运行，检查 `run_celery_worker.py` 是否成功启动了 metrics server。

---

## HighRedisMemory

**含义：** Redis 内存使用超过 `maxmemory`（128MB）的 80%，持续 10 分钟。**warning**

**影响：** Redis 配置为 `noeviction`，内存写满后所有写操作都会失败。这会导致 Celery 投递任务失败、缓存与 API Key 节流失效，进而引发 API 5xx。

**排查：**
```bash
dc exec jobpilot-redis redis-cli info memory | grep -E 'used_memory_human|maxmemory_human'
dc exec jobpilot-redis redis-cli llen celery
dc exec jobpilot-redis redis-cli --bigkeys
```

**常见原因与处理：**
- **Celery 队列积压：** 见 [CeleryQueueBacklog](#celeryqueuebacklog)。
- **Celery 结果 / 缓存 key 没有设置 TTL：** 用 `--bigkeys` 找到大 key，确认可以删除后清理，并在代码里补上过期时间。
- **确实需要更多内存：** 调大 `docker-compose.prod.yml` 中的 `--maxmemory`（同时确认 VPS 内存余量），然后重新部署。
