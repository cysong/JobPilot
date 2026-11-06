# JobPilot SLO / SLI / Error Budget

> 对应 [sre_plan.md](sre_plan.md) 阶段 1「定义并文档化 SLO / SLI / Error Budget」。
> 告警处理流程见 [runbooks.md](runbooks.md)。

**Last Updated:** 2026-11-06

---

## 1. 前提与约束

| 约束 | 影响 |
|---|---|
| 单用户、低流量（每天几十到几百个真实请求） | 短窗口内样本极少，`histogram_quantile` 返回的是桶边界而非真实分位数 → SLI 一律用「好事件 / 总事件」比例，不用分位数 |
| Prometheus 保留期 15 天（`--storage.tsdb.retention.time=15d`） | SLO 窗口取 **滚动 14 天**，保证整窗数据都在库里 |
| Instrumentator 默认统计所有路由，包含 Prometheus 每 15s 抓取的 `/metrics` 和容器 healthcheck 的 `/health` | 这些合成流量占总请求的绝大多数，会把错误率稀释到接近 0 → API 类 SLI 必须排除 `handler=~"/metrics\|/health"` |
| LLM / 解析等耗时工作在 Celery 里异步执行 | API 延迟 SLI 只衡量同步接口；异步工作由任务成功率 SLI 覆盖 |

---

## 2. SLI 与 SLO

窗口统一为 **滚动 14 天**。

| # | 名称 | SLI（好事件 / 总事件） | SLO | 14 天 Error Budget |
|---|---|---|---|---|
| 1 | API 可用性 | 非 5xx 请求 / 全部请求（排除 `/metrics`、`/health`） | **99.5%** | 0.5% 的请求（折算为时间约 100 分钟全量不可用） |
| 2 | API 延迟 | 耗时 ≤ 1s 的请求 / 全部请求（同上排除） | **95%** | 5% 的请求可以慢于 1s |
| 3 | 后台任务成功率 | Celery `success` / (`success` + `failure`)，`retry` 不计入 | **98%** | 2% 的任务最终失败 |
| 4 | LLM 调用成功率 | `outcome="ok"` / 全部 LLM 调用 | **95%** | 5% 的调用失败（含 timeout / ratelimit） |

**说明：**

- **延迟阈值选 1s 而不是 sre_plan 中最初写的 P95 < 2s：** `http_request_duration_seconds` 只有 `0.1 / 0.5 / 1` 三个桶，但带 `handler` 标签，可以排除合成流量；`_highr` 版本桶更细，却没有 `handler` 标签。1s 也和现有 `APISlowRequests` 告警的阈值一致。
- **LLM 成功率目标比较宽松：** 失败多数来自上游 Provider（限流、超时），我们能控制的只有重试和降级策略。
- **Resend 邮件只作为参考指标，不设 SLO：** 量太小（每月几封），而且已经由 `ResendDeliveryFailure` 告警覆盖。

---

## 3. PromQL

这些查询可以直接用作 Grafana 面板，后续也可以改写成 recording rules。

### 3.1 API 可用性

```promql
# SLI (14d)
1 - (
  sum(increase(http_requests_total{handler!~"/metrics|/health", status=~"5.."}[14d]))
  /
  sum(increase(http_requests_total{handler!~"/metrics|/health"}[14d]))
)

# Remaining error budget (1 = untouched, 0 = exhausted, < 0 = overspent)
1 - (
  (
    sum(increase(http_requests_total{handler!~"/metrics|/health", status=~"5.."}[14d]))
    /
    sum(increase(http_requests_total{handler!~"/metrics|/health"}[14d]))
  ) / (1 - 0.995)
)
```

### 3.2 API 延迟

```promql
sum(increase(http_request_duration_seconds_bucket{handler!~"/metrics|/health", le="1.0"}[14d]))
/
sum(increase(http_request_duration_seconds_count{handler!~"/metrics|/health"}[14d]))
```

> `le` 标签的值是浮点字符串（`"1.0"`），如果查不到数据，用 `le=~"1(\\.0)?"` 兜底。

### 3.3 后台任务成功率

```promql
sum(increase(jobpilot_celery_task_total{event="success"}[14d]))
/
sum(increase(jobpilot_celery_task_total{event=~"success|failure"}[14d]))

# Per-task breakdown to find who is burning the budget
sum by (task_name) (increase(jobpilot_celery_task_total{event="failure"}[14d]))
```

### 3.4 LLM 调用成功率

```promql
sum(increase(jobpilot_llm_call_total{outcome="ok"}[14d]))
/
sum(increase(jobpilot_llm_call_total[14d]))

# Failure breakdown by agent / provider / outcome
sum by (agent_id, provider, outcome) (increase(jobpilot_llm_call_total{outcome!="ok"}[14d]))
```

---

## 4. Error Budget 策略

以「剩余预算」为准，每周看一次 Grafana（或者在收到告警时看）。

| 剩余预算 | 动作 |
|---|---|
| > 50% | 正常迭代功能 |
| 0 – 50% | 排查主要的预算消耗来源（按 handler / task_name / agent_id 拆分），记录到 [issues.md](issues.md) |
| < 0（已透支） | 暂停新功能，优先修复可靠性问题，直到 14 天窗口滚回 SLO 以内 |

**例外情况：** 下面这些事件消耗的预算记录在案，但不触发冻结：
- 上游完全不可控的故障，例如 Supabase 或 LLM Provider 的全面宕机
- 计划内的维护窗口

---

## 5. 与告警的关系

现有告警（[deploy/prometheus/alert_rules.yml](../deploy/prometheus/alert_rules.yml)）是「症状 + 阈值」型，目标是尽快发现问题。SLO 的目标是衡量长期可靠性，两者互补：

| SLO | 对应告警 |
|---|---|
| API 可用性 | `APIHighErrorRate`、`APIDown` |
| API 延迟 | `APISlowRequests` |
| 后台任务成功率 | `CeleryTaskFailureRate`、`CeleryRetryStorm`、`CeleryQueueBacklog` |
| LLM 调用成功率 | `LLMCallFailureRate` |

### 已知差距与后续改进

1. ~~**`APIHighErrorRate` / `APISlowRequests` 被合成流量稀释**~~（2026-11-06 已修复）：两条规则都已排除 `/metrics` 和 `/health`。排除后分母很小，所以又加了最小事件数保护：5 分钟内至少 3 个 5xx、10 分钟内至少 5 个请求，避免单个异常请求就触发告警。
2. **Burn-rate 告警：** 低流量下短窗口不稳定，暂时不做。等流量上来或接入 AWS 后，再引入多窗口 burn-rate 告警（如 1h/5m 14.4x、6h/30m 6x）。
3. **Grafana Error Budget 面板：** 把第 3 节的查询加到 `jobpilot.json` dashboard。
4. **延长保留期：** 如果想改用 28 / 30 天窗口，需要把 Prometheus 保留期调到 ≥ 35d。按当前的指标基数，磁盘开销可以忽略。
