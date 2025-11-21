# JobPilot + Spec-kit 升级设计方案

## 0. 范围与目标
- 在现有 “Frontend + FastAPI + Celery + Workflow + AI Agent” 架构上接入 spec-kit 作为统一 AI 调用层。
- 重点：Prompt 管理、模型网关整合、调用观测与评估、测试/回放、利用内置能力。
- 保持最小改动，支持灰度/回滚；仅将日志写入 DB（不接监控栈）；直连兜底通过配置文件开关。

## 1. 架构叠加（变化点）
- 调用路径：Front（不变） → FastAPI/Workflow → **Spec-kit Gateway（新增）** → LLM Provider（DeepSeek / OpenAI / …）。
- 存储/日志：PostgreSQL 新表 AiCalls（直接替换原 AiUsage，无需迁移），不输出到监控栈或外部日志管线。
- 版本关联：`config_version` 继续使用；`prompt_version` 与 `config_version` 解耦，在同一配置下可灰度/切换提示版本，实际版本写入调用记录。

### 调用数据流
```
[FastAPI Router]
      |
      v
[Workflow Executor]
      |
      v
[Spec-kit Gateway]
  - Prompt 渲染 & 版本标签
  - 策略中间件（超时/重试/审计）
  - 调用观测（写 AiCalls）
      |
      v
[LLM Provider SDKs]
```

## 2. 组件与主要变化
- **Spec-kit Gateway Service（新增层）**  
  统一模型路由、提示渲染、策略执行、日志/审计；提供内部 SDK 供 `app/modules/ai_agent/service.py` 调用。
- **Prompt Store（新增）**  
  manifest + 模板，含 `prompt_id`、`prompt_version`、变量声明、适用模型；渲染时校验变量，渲染结果附带 `prompt_id/prompt_version`。
- **模型网关**  
  适配 DeepSeek、OpenAI 等，统一参数（超时、重试、max_tokens、temperature）。路由策略可按 `workflow_type`/`operation`/`tier`/灰度配置选择模型，并保留覆盖开关。
- **观测与评估**  
  调用日志写入 AiCalls：tokens、cost、latency、model、prompt 版本、执行链路关联，用于后续查询/报表。
- **测试与回放**  
  Mock/Replay 在 CI/Stage 使用，降低外部依赖；断言延迟、tokens、必备字段。

## 3. 数据模型：AiCalls（直接替换 AiUsage）
- 表：`ai_calls`
- 字段建议：
  - `id` (pk)  
  - `user_id` (可选)  
  - `workflow_execution_id`, `task_id`  
  - `operation`（job_analysis / resume_tailor / cover_letter / …）  
  - `prompt_id`, `prompt_version`  
  - `model`, `provider`  
  - `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`  
  - `estimated_cost`  
  - `latency_ms`  
  - `status`（success / timeout / ratelimit / error / other）  
  - `retry_count`  
  - `created_at`
- 索引建议：
  - `(workflow_execution_id, task_id)`
  - `(operation, created_at)`
  - `(prompt_id, prompt_version)`
  - `(model)`
  - `(status, created_at)`

## 4. Prompt 管理（与 config_version 解耦）
- 存储：`prompts/manifest.yaml` + 业务分目录模板（job_analysis, resume_tailor…）。
- 版本策略：显式 `prompt_version`，禁止覆盖；同一 `config_version` 下可灰度/AB 提示版本，调用记录写入实际 `prompt_version`。
- 渲染校验：缺失/多余变量直接失败；渲染后附带 `prompt_id/prompt_version` 透传到 Gateway 和 AiCalls。

### manifest.yaml 示例
```yaml
prompts:
  - id: job_analysis_base
    version: "v1.0.0"
    model_default: "deepseek-chat"
    path: "job_analysis/v1.prompt.md"
    variables:
      - name: job_markdown
        type: string
        required: true
      - name: language
        type: string
        required: false
        default: "zh"

  - id: resume_tailor_light
    version: "v1.0.0"
    model_default: "gpt-4o"
    path: "resume_tailor/v1.prompt.md"
    variables:
      - name: resume_text
        type: string
        required: true
      - name: job_requirements
        type: string
        required: true
```

## 5. 模型网关集成
- 改动点：`app/modules/ai_agent/service.py` 与 agents/tools 统一通过 Gateway。
- 接口约束：统一返回结构（text|json + usage + meta），错误码统一（rate_limit/timeout/auth/validation）。
- 重试策略：仅限流/超时重试；业务错误不重试；总耗时受 Celery 任务超时约束。

## 6. 观测与评估（DB 版）
- 写入：所有调用记录入 AiCalls；后续基于 DB 查询/物化视图做报表。
- 维度：workflow_type + config_version + prompt_version + model + status + latency/tokens/cost。
- 不接监控栈：当前无需 Prom/Grafana/ELK 配置，先保证数据齐全、查询可用。

## 7. 测试与发布
- 环境策略：Dev/CI 用 replay/mock；Stage 小流量真实调用；Prod 分批放量。
- 覆盖用例：主链路（job_analysis、application_generation）、异常（限流、超时）、变量校验失败、模型切换回退。
- 回滚：模型/提示版本/禁用 Gateway 的开关可快速回退；直连兜底由配置文件开关控制。

## 8. 建议目录与文件结构（变化部分）
```
backend/
  app/
    core/
      spec_kit/               # 独立模块
        gateway.py            # 统一入口，策略/路由/重试
        client.py             # 封装 DeepSeek/OpenAI 调用
        logging.py            # 记录 AiCalls
        prompt_store.py       # manifest 解析与渲染
    modules/
      ai_agent/               # 与 spec_kit 并列
        service.py            # 改为调用 spec-kit gateway
        prompts/              # 提示模板与 manifest
          manifest.yaml
          job_analysis/
            v1.prompt.md
            v2.prompt.md
          resume_tailor/
            v1.prompt.md
docs/
  spec-kit-upgrade.md         # 本文档
```

## 9. 渐进落地顺序
1) 接入最小网关（单模型 DeepSeek），记 AiCalls，保留直连兜底开关（配置文件）。  
2) 引入 prompt manifest + 渲染校验，在 job_analysis 主链路打标签并写 AiCalls。  
3) 扩展到 application_generation，接入超时/重试策略；建立 DB 查询/报表。  
4) 启用 replay/mock 于 CI，补充异常/回退用例。  
5) 多模型路由与小流量灰度；完善回滚开关与运维手册。  

