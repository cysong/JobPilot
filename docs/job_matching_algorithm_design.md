# JobPilot 岗位匹配算法设计方案

> **版本**: v1.4
> **日期**: 2026-04-21
> **状态**: 设计阶段，待实施
> **范围**: JD ↔ 简历 匹配算法整体架构设计
>
> v1.4 更新：
> - Embedding 维度 **3072 → 1536**（text-embedding-3-large `dimensions=1536`），让 pgvector HNSW 可建索引
> - L1 硬过滤增加 **职级差距 ≥ 3 直接排除**（依赖 `job_analyses.seniority` + `resumes.analysis_result.total_experience_years`）
> - 失败态处理下放到 §14.1：L0/L3 各表加 `*_status` / `*_error` 字段，明确重试与中间态不展示
>
> v1.3 更新：embedding 载体字段重命名 `summary` → **`profile_text`**，`summary_version` → **`profile_version`**。
>
> v1.2 更新：v2 结果**新建独立表 `job_match_recommendations`**；v1 匹配流水线整体下线。
>
> v1.1 更新：对齐现有表结构与代码路径；JD profile/embedding 入 `job_analyses`（`seek_jobs` 只读）。

---

## 〇、现状与约束（实施前必读）

### 0.1 不可动的边界

| 项 | 状态 |
|---|---|
| `seek_jobs` 表 | **只读**，由外部爬虫维护，不加列、不改结构 |
| `users.id` / `resumes.id` 主键 | 已上线，类型不变（int / String(255) UUID） |
| `user_job_matches` 表（v1） | **整体下线**，保留观察期后独立迁移 drop，不做数据迁移 |
| `job_match_recommendations` 表（v2） | **新建**，干净 schema，无 v1 列的语义漂移 |

### 0.2 已经可用的结构化产物

| 能力 | 载体 | 由谁生成 |
|------|------|--------|
| JD 结构化字段（required_skills / seniority / hiring_priorities 等） | `job_analyses` 表 | `job_analyzer` agent |
| JD 中文翻译 | `job_analyses.cn_content` | `universal_translator` |
| 简历结构化字段（technical_skills / work_experiences / location 等） | `resumes.analysis_result` | `resume_analyzer` agent |
| 简历目标岗位（受控词表） | `resumes.target_job_titles` | `resume_analyzer` |
| 用户技能聚合 | `user_skills` / `resume_skills` | 简历分析抽取 |
| 用户偏好 | `users.preferences` JSONB | 用户自填 |

**v2 方案直接复用以上产物**，不重复建 agent。

### 0.3 要停用的 v1 组件（一次性清理清单）

| 组件 | 位置 | 动作 |
|------|------|------|
| `pull_unmatched_jobs` 定时调度 | `matching/pull.py` + Celery beat | 从 beat 移除；函数可删或保留空壳 `return {"status":"disabled"}` |
| `calculate_job_user_matches_task` v1 实现 | `matching/tasks.py` | 整体替换为 v2 实现（函数名保留） |
| `match_user_recent_jobs_task` v1 实现 | `matching/tasks.py` | 整体替换（函数名保留） |
| `analyze_match_with_ai_task` | `matching/tasks.py` | 替换为调用新 `match_judger` agent，写入新表 |
| `calculate_skill_match_score` | `matching/service.py` | **删除** |
| `calculate_resume_match_score` | `matching/service.py` | **删除** |
| `find_best_resume_for_user`（加权版） | `matching/service.py` | **删除**，改向量版 |
| `prefilter_candidates_by_title` | `matching/service.py` | 保留，作为 L1 辅助 |
| `user_has_title_target` | `matching/service.py` | 保留 |
| `UserJobMatch` ORM + `UserJobMatchRepository` | `matching/models.py` / `matching/repository.py` | 标记 `# DEPRECATED v1`，不再被调用；随 v1 表一起在独立迁移中删除 |
| `MatchAnalysis` schema | `agent_configs/schemas.py` | **删除**（由新 `MatchJudgment` 取代） |
| `match_analyzer.yaml` | `agent_configs/config/` | **删除**（改名新建 `match_judger.yaml`） |
| `SKILL_MATCH_THRESHOLD = 40` / `MAX_CANDIDATES_PER_JOB = 100` | `core/config.py` | **删除**，新增 `TOP_N_VECTOR_CANDIDATES = 30` |
| `UserJobMatchResponse` / `UserJobMatchDetailResponse` | `jobs/schemas.py` | 新建 `JobMatchResponse` 对应新表；旧 schema 删或暂保留直到前端切完 |
| 推荐列表 API | 现有路由 | 切到查 `job_match_recommendations` 新表 |
| `user_job_matches` 表 | Postgres | **不做数据迁移**；代码切换后 1-2 周观察期，再独立迁移 `DROP TABLE` |

### 0.4 要复用的 v1 壳

| 组件 | 作用 |
|------|------|
| `pull_unmatched_jobs`（Celery beat） | 5 分钟一次从 `job_analyses.updated_since` 拉新岗位触发匹配 |
| `TaskType.JOB_USER_MATCHING` | 工作流任务类型，不变 |
| `calculate_job_user_matches_task` 任务壳 | 保留，**替换内部实现**为 L1→L2→L3 |
| `match_user_recent_jobs_task` | 保留，替换内部实现为"新简历触发反向匹配" |
| `analyze_match_with_ai_task` | 保留，替换其调用的 agent 与 schema |
| `UserJobMatchRepository.upsert` | 保留，入参适配新语义 |

---

## 一、背景与目标

JobPilot 需要根据用户简历，从持续入库的岗位中识别出"真正适合用户的岗位"并推送。当前场景的特征：

| 维度 | 取值 |
|------|------|
| 市场 | 新西兰（Seek / LinkedIn 等） |
| 岗位规模 | 约 10,000，每日增量 100-500 |
| 用户规模 | 极少（开发期），未来 500+ |
| 行为数据 | 接近零（冷启动常态） |
| 实时性 | 异步批处理，无实时要求 |
| 核心诉求 | 让用户产生"这就是我想申请的工作"的强烈认同 |
| 评估指标 | 用户申请意愿（精度 > 召回，宁缺勿滥） |

### 核心问题

回答的是「**新岗位值得推给哪些用户**」，而不是「**给用户凑够 Top 20**」。
没合适的用户就不推；数量不是目标，精度才是。

---

## 二、核心设计原则

1. **岗位驱动**：新岗位进来 → 匹配用户池 → 写入推荐表；不是用户请求 → 从存量岗位找 Top K
2. **向量做粗排，LLM 做精判**：两者功能不重叠，都不可替代
3. **简历级画像 + 用户级约束**：一个用户 N 份简历各自独立向量化；地点/签证等硬约束在用户级
4. **宁缺勿滥**：没合适的就不推，不为了数量凑数
5. **LLM 精判是核心算子**：它是 Cross-Encoder 的零样本替代，是真正判断胜任度的组件
6. **端到端文本相似度 > 字段加权求和**：自适应权重永远调不好，embedding 能吃整段语义
7. **最小改动优先**：能复用的表、任务、agent 都复用；只在数据结构确实不够表达时才加列

---

## 三、关键认知：向量余弦衡量的是什么？

### 3.1 向量余弦 ≠ 胜任度

两段文本的 embedding 余弦衡量的是：

> 在预训练模型的语义空间中，这两段文本表达的「话题、实体、技能、场景」的重合程度。

JD 写的是「我需要什么」（"we want", "must have", "you will..."），简历写的是「我有什么」（"I built", "I led", "I have..."）。
**即使一个人 100% 满足岗位要求，两段文本的余弦也不会是 1.0**，现实上限约 0.75。

| 场景 | 典型余弦值 |
|------|-----------|
| 同一份 JD 自己和自己 | 1.00 |
| 两份同类 JD | 0.85-0.92 |
| **完美匹配的 JD vs 简历** | **0.55-0.75** |
| 相关但不完全匹配 | 0.45-0.60 |
| 不相关 | 0.30-0.45 |

### 3.2 结论：向量只做粗排，胜任度交给 LLM

```
                粗排工具                       精排工具
向量余弦 ────────────────────                ───────────────── LLM 精判
(相似度)                                              (胜任度)
话题重合度                                           综合推理判断
快、便宜、可索引                                      慢、贵、准确
绝对分不可信                                         分数有语义
能做 10K → 200                                       做 200 → 20
```

两者功能不重叠，都不可替代。**不要设绝对余弦阈值**（如 "> 0.7"），用相对排序（top N）。

### 3.3 LLM 精判的本质

LLM 读一份 JD 和一份 Profile，做的事本质是：

> 模拟一个资深招聘顾问同时看这两份文档，回答"这个人投这个岗靠不靠谱"。

这是**推理判断（Reasoning）**，不是相似度。它显式处理技能、职级、方向、领域等维度，产出有明确语义的胜任度分数。

**LLM 精判 = Cross-Encoder 的零样本版本**：同时读两份文档，直接输出匹配分。

---

## 四、整体架构（对齐现有任务链路）

```
┌──────────────────────────────────────────────────────────────┐
│                  离线准备（事件驱动，一次性）                       │
├──────────────────────────────────────────────────────────────┤
│  analyze_job_task 完成 → job_analyses 行写入                    │
│       ↓ 新增后置步骤（同事务 or 续跑 Celery chain）               │
│  [L0-J] LLM 生成 profile_text（输入 = job.content + job_analyses │
│         结构化字段）                                              │
│       ↓                                                        │
│  [L0-J] embedding(profile_text) = vector(1536)                 │
│       ↓ 更新 job_analyses.profile_text / .embedding             │
│                                                                │
│  analyze_resume_task 完成 → resumes.analysis_result 写入         │
│       ↓ 新增后置步骤                                             │
│  [L0-R] LLM 生成 profile_text（输入 = resume.content +           │
│         analysis_result 结构化字段 + target_job_titles）          │
│       ↓                                                        │
│  [L0-R] embedding(profile_text) = vector(1536)                 │
│       ↓ 更新 resumes.profile_text / .embedding                  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│        在线匹配：新岗位 J 触发（复用 pull_unmatched_jobs）          │
├──────────────────────────────────────────────────────────────┤
│  pull_unmatched_jobs  ──▶  TaskType.JOB_USER_MATCHING           │
│       ↓                                                        │
│  calculate_job_user_matches_task（v2 实现）                      │
│                                                                │
│  [L1] 用户池硬过滤（SQL，毫秒级）                                  │
│       - resumes.is_draft=false AND is_deleted=false             │
│       - resumes.embedding IS NOT NULL AND profile_status='ok'   │
│       - 职级差距 ≥ 3 硬拒（详见 §9.4）                             │
│       - resumes.target_job_titles 含 job_analyses.normalized_job_title│
│         （保留 prefilter_candidates_by_title 作辅助，匹配不上 fallback）│
│       - users.preferences.job_locations ∩ seek_jobs.location_city│
│         （可选；为空时跳过）                                       │
│       500 用户 → 30-100 候选                                     │
│       ↓                                                        │
│  [L2] 向量粗排（pgvector cosine，按用户聚合取最大）                │
│       SELECT user_id, resume_id, 1 - (r.embedding <=> :job_emb) │
│         AS sim FROM resumes r WHERE ...                         │
│       按 user_id 取 max(sim) → 相对 top N（默认 30）              │
│       ↓                                                        │
│  [L3] LLM 精判（沿用 analyze_match_with_ai_task 的壳）            │
│       输入：(job_analyses.profile_text, resumes.profile_text[best])│
│       输出：rubric dimensions + decision + one_line_reason       │
│       ↓                                                        │
│  [L4] JobMatchRecommendationRepository.upsert（新表）             │
│       - vector_sim          = L2 cosine [0,1]                   │
│       - resume_id           = L2 argmax                         │
│       - per_resume_sims     = {resume_id: sim}                  │
│       - overall_score       = L3 rubric [0,10]                  │
│       - decision            = recommend / borderline / reject   │
│       - dimensions / one_line_reason / evidence                 │
│       - algorithm_version   = 'v2.0.0'                          │
│         前端列表仅查 decision='recommend' ORDER BY overall_score │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│    反向触发：新简历 R 上传（复用 match_user_recent_jobs_task）      │
├──────────────────────────────────────────────────────────────┤
│  analyze_resume_task 完成 → L0-R 生成 profile_text + embedding   │
│       ↓                                                        │
│  对「最近 30 天活跃 job_analyses 池」做粗排（不扫全量）             │
│       ↓                                                        │
│  top 30 进 LLM 精判，upsert user_job_matches                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 五、数据模型（以最小迁移对齐现有表）

### 5.1 岗位侧：给 `job_analyses` 加 4 列

```sql
-- Alembic: add embedding fields to job_analyses
ALTER TABLE job_analyses
    ADD COLUMN profile_text      TEXT,         -- 标准化岗位画像文本（非原始 JD 摘要）
    ADD COLUMN embedding         vector(1536),
    ADD COLUMN embedding_model   TEXT,
    ADD COLUMN profile_version   TEXT;         -- profile_text 生成 prompt 的版本号

CREATE INDEX job_analyses_emb_hnsw_idx
    ON job_analyses USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

-- 注：seek_jobs 只读，不加任何列；向量相关一律挂 job_analyses
-- 注：命名选 profile_text 而非 summary，避免与 seek_jobs.abstract / resumes.analysis_result 混淆
--     且语义更准确——这不是内容摘要，是为 embedding 对齐而生的规范化 profile（§7）
```

ORM（`app/modules/jobs/models.py: JobAnalysis`）新增字段：
```python
profile_text:     Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
embedding:        Mapped[Optional[list]]  = mapped_column(Vector(1536), nullable=True)
embedding_model:  Mapped[Optional[str]]   = mapped_column(String(100), nullable=True)
profile_version:  Mapped[Optional[str]]   = mapped_column(String(20), nullable=True)
```

### 5.2 简历侧：给 `resumes` 加 4 列

```sql
ALTER TABLE resumes
    ADD COLUMN profile_text      TEXT,         -- 标准化候选人画像文本
    ADD COLUMN embedding         vector(1536),
    ADD COLUMN embedding_model   TEXT,
    ADD COLUMN profile_version   TEXT;

CREATE INDEX resumes_emb_hnsw_idx
    ON resumes USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL
      AND is_deleted = FALSE
      AND is_draft   = FALSE;
```

**不新增**的字段（已有）：`target_job_titles`（L1 辅助）、`analysis_result`（profile_text 生成的输入）、`analysis_version`。

### 5.3 匹配结果表：**新建 `job_match_recommendations`，v1 表下线**

v1 `user_job_matches` 表的列语义与 v2 差异过大（skill_match_score 强绑加权、ai_analysis 装的是 strengths/... 非 rubric），复用会留下永久的语义漂移。直接新建 v2 专属表，结构按 v2 pipeline 设计；v1 表不做数据迁移，代码切换后保留观察期，再由独立迁移 drop。

```sql
-- Alembic 迁移 B（在迁移 A 加列之后）
CREATE TABLE job_match_recommendations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           INTEGER        NOT NULL REFERENCES users(id)      ON DELETE CASCADE,
    job_id            INTEGER        NOT NULL REFERENCES seek_jobs(id)  ON DELETE CASCADE,
    resume_id         VARCHAR(255)   NOT NULL REFERENCES resumes(id)    ON DELETE CASCADE,

    -- L2 粗排
    vector_sim        REAL           NOT NULL,          -- cosine [0,1]
    per_resume_sims   JSONB          NOT NULL DEFAULT '{}'::jsonb,
    embedding_model   TEXT           NOT NULL,
    profile_version   TEXT           NOT NULL,

    -- L3 精判（L2 完成后异步填充）
    overall_score     REAL,                             -- 0-10
    decision          TEXT,                             -- recommend/borderline/reject（代码按 overall_score 切档，见 §8.6）
    dimensions        JSONB,                            -- {skill_overlap:{score,evidence}, ...}
    one_line_reason   TEXT,
    llm_model         TEXT,
    prompt_version    TEXT,

    algorithm_version TEXT           NOT NULL DEFAULT 'v2.0.0',
    l2_finished_at    TIMESTAMPTZ    NOT NULL,
    l3_finished_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),

    UNIQUE (user_id, job_id)
);

CREATE INDEX idx_jmr_user_decision_score
    ON job_match_recommendations (user_id, decision, overall_score DESC);

CREATE INDEX idx_jmr_job            ON job_match_recommendations (job_id);
CREATE INDEX idx_jmr_recommend_recent
    ON job_match_recommendations (created_at DESC)
    WHERE decision = 'recommend';

CREATE INDEX idx_jmr_pending_l3
    ON job_match_recommendations (l2_finished_at)
    WHERE l3_finished_at IS NULL;
```

**ORM**（新增到 `matching/models.py`，与旧 `UserJobMatch` 并存直到 drop）：
```python
class JobMatchRecommendation(Base, TimestampMixin):
    __tablename__ = "job_match_recommendations"

    id: Mapped[str]             = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int]        = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int]         = mapped_column(ForeignKey("seek_jobs.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[str]      = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))

    vector_sim: Mapped[float]
    per_resume_sims: Mapped[dict]   = mapped_column(JSONB, default=dict)
    embedding_model: Mapped[str]    = mapped_column(String(100))
    profile_version: Mapped[str]    = mapped_column(String(20))

    overall_score: Mapped[Optional[float]]
    decision: Mapped[Optional[str]] = mapped_column(String(20))
    dimensions: Mapped[Optional[dict]] = mapped_column(JSONB)
    one_line_reason: Mapped[Optional[str]] = mapped_column(Text)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(20))

    algorithm_version: Mapped[str]  = mapped_column(String(20), default="v2.0.0")
    l2_finished_at: Mapped[datetime]
    l3_finished_at: Mapped[Optional[datetime]]

    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_jmr_user_job"),)
```

**Repository 新建**：`JobMatchRecommendationRepository.upsert_l2()` / `update_l3()` / `list_recommendations_for_user()`。

**对外查询**（前端/API）：
```sql
SELECT *
FROM job_match_recommendations
WHERE user_id = :uid
  AND decision = 'recommend'
ORDER BY overall_score DESC, created_at DESC
LIMIT :limit OFFSET :offset;
```

**v1 表下线时间线**：
1. 部署 v2 代码：v1 pipeline 全部停跑，新 L1/L2/L3 只写新表
2. 前端切到新表 API
3. 观察期 1-2 周，确认无脏依赖
4. 独立 Alembic 迁移：`DROP TABLE user_job_matches CASCADE`，同时从 ORM 删除 `UserJobMatch` / `UserJobMatchRepository`

### 5.4 用户硬约束：复用 `users.preferences` JSONB，不加列

现有 JSONB 只有 `job_locations` / `salary_expectation`。v2 **不强行扩展 JSONB schema**：
- 地点约束：`preferences.job_locations` ∩ `seek_jobs.location_city` —— 空即跳过
- 职级 / 签证 / 相对经验：**放到 L3 LLM 精判的 rubric**，让模型打分，避免硬过滤误杀
- 如果后续确有需要（例如签证强硬过滤），再扩展 JSONB，UserPreferences Pydantic schema 同步加字段

---

## 六、多简历的处理

**一个用户可能有 N 份正式简历（Backend / QA / DevOps），匹配时需要两个维度：选对用户 + 推荐对简历。**

### 6.1 设计思路

- **一个用户 = N 个简历画像**，各自独立生成 `resumes.profile_text + resumes.embedding`
- **硬约束在用户级**（`users.preferences`），简历级只管职业方向
- 只对 `is_draft=FALSE AND is_deleted=FALSE` 的正式简历参与匹配

### 6.2 匹配流程（pgvector 版）

```sql
-- L2: 给定 job_emb，对候选用户按用户粒度取最大 cosine
WITH candidate_sims AS (
    SELECT
        r.user_id,
        r.id AS resume_id,
        1 - (r.embedding <=> :job_emb) AS sim
    FROM resumes r
    WHERE r.is_draft = FALSE
      AND r.is_deleted = FALSE
      AND r.embedding IS NOT NULL
      AND r.user_id = ANY (:candidate_user_ids)  -- L1 过滤后
)
SELECT DISTINCT ON (user_id)
    user_id, resume_id, sim
FROM candidate_sims
ORDER BY user_id, sim DESC;
```

**每个用户按其最匹配简历的分数参与排序**，取 top N（默认 30）。出 LLM 精判时只送这一份简历的 profile_text。
输出的匹配结果天然带"该用哪份简历申请"——就是 `recommended_resume_id`。

### 6.3 成本与规模

- LLM 调用次数不随简历数线性增长，仍是每个岗位调一次精判
- 3 份简历 = 3 次 embedding（一次性），pgvector cosine 几乎免费

---

## 七、L0 摘要生成：让 JD 和简历"说同一种话"

**这一步是保证 L2 向量相似度有效的关键**——把 JD 的"需求语言"和简历的"经历语言"都转成同一种**岗位画像语言**，显著缩小文本体裁差。

效果：完美匹配的 JD-Profile 余弦从 ~0.65 提升到 ~0.78。仍不是 1.0，但**作为粗排已足够拉开差距**。

### 7.1 工程形态

- **新增 agent**：`job_profile_writer`、`resume_profile_writer`（各自 YAML + schema）
- **挂接点**：
  - `job_profile_writer` 在 `analyze_job_task` 成功后由同一任务续跑（或作为 Celery chain 的下一步）
  - `resume_profile_writer` 同理挂在 `analyze_resume_task` 后
- **Embedding 调用**：新建 `app/core/llm/embedding.py`，封装 OpenAI `text-embedding-3-large` **并传 `dimensions=1536`**（3072 维超过 pgvector HNSW 2000 维上限；large@1536 比 small@1536 仍有约 3% MTEB 优势，成本按 token 计费与 3072 同）

### 7.2 JD 摘要 Prompt（输入复用 job_analyses 结构化字段）

```
[System]
You generate standardized job profiles from job descriptions.
Output a 200-400 word third-person profile following EXACTLY this structure:

Role: <standardized title and seniority>
Domain: <engineering / data / product / design / devops / qa / management>
Core technologies: <list key required techs, max 10>
Key responsibilities: <3-5 bullets in "owns / leads / builds" voice>
Experience bar: <years range, specific experience types>
Nice-to-have: <preferred skills if mentioned>
Work context: <remote/hybrid/onsite, location, company stage if clear>

Write in neutral third person. Do NOT use "we want", "you will", "must have".
Use "requires", "involves", "expects".

[User]
RAW JD:
<seek_jobs.content>

STRUCTURED FIELDS (from job_analyses):
- normalized_job_title: <...>
- seniority: <...>
- required_skills: [...]
- preferred_skills: [...]
- tech_stack: [...]
- experience_years: <...>
- key_responsibilities: [...]
- hiring_priorities: [...]
- location: <seek_jobs.location_label>
- work_types: <seek_jobs.work_types_label>
```

### 7.3 简历摘要 Prompt（输入复用 resumes.analysis_result）

**关键：输出结构与 JD 摘要完全一致**。

```
[System]
You generate standardized candidate profiles from resumes.
Output a 200-400 word third-person profile following EXACTLY this structure:

Role: <current/target title and seniority>
Domain: <engineering / data / product / design / devops / qa / management>
Core technologies: <list demonstrated techs with proficiency hints>
Key accomplishments: <3-5 bullets in "built / led / shipped" voice>
Experience: <total years, specific experience types>
Additional skills: <other demonstrated competencies>
Work preferences: <location, visa status, open to remote/hybrid>

Write in neutral third person. Do NOT use "I", "my".
Use "has", "demonstrates", "led", "built".

[User]
RAW RESUME:
<documents.content>

STRUCTURED FIELDS (from resumes.analysis_result):
- current_title: <...>
- total_experience_years: <...>
- target_job_titles: [...]           (from resumes.target_job_titles)
- technical_skills: [{name, proficiency}, ...]
- soft_skills: [...]
- work_experiences: [{company, role, duration, ...}]
- quantified_achievements: [...]
- location: <...>
- work_right: <...>
```

### 7.4 为什么这样做

- 强制同样的章节结构 → embedding 模型更容易对齐
- 强制同样的语态（第三人称、动词） → 消除 "we want" vs "I have" 造成的风格差
- 强制同样的领域分类 → domain 字段可以后续做粗过滤

---

## 八、L3 LLM 精判：胜任度的真正算子

### 8.1 Prompt 设计

替换现有 `match_analyzer` agent。新 agent 名：`match_judger`（或 `match_analyzer` 原名保留但升 schema 版本到 v2.0.0）。

```
[System]
You are a senior recruitment consultant evaluating whether a candidate
is a good fit for a specific role. You MUST follow the rubric below
and return a structured JSON decision.

=== SCORING RUBRIC (0-10 per dimension) ===

skill_overlap:
  10: Has all required skills at required proficiency or higher
   8: Missing 1 required skill OR proficiency slightly below
   6: Missing 2 required skills but has equivalent experience
   4: Half of required skills covered
   2: Only peripheral skills overlap
   0: No meaningful skill overlap

seniority_fit:
  10: Seniority matches (Senior → Senior, or 1 level up from candidate)
   7: Candidate 1 level below job, but strong experience
   5: Candidate 1 level above job (overqualified, still OK)
   3: 2+ levels mismatch
   0: Massive mismatch (Junior → Principal)

career_direction:
  10: Candidate's target titles exactly match this role family
   7: Adjacent role family (e.g. Full Stack → Backend)
   4: Related domain but different specialization
   0: Clearly different career track

domain_relevance:
  10: Candidate comes from same industry/domain with proven track record
   7: Related domain, transferable experience evident
   4: Different domain but skill transfer plausible
   0: Completely unrelated domain

=== ANCHOR EXAMPLES ===

Example A (overall=9.2, recommend):
  Job: "Senior Python Backend Engineer at fintech, 5+ years FastAPI/Postgres"
  Profile: "Senior Full Stack Engineer with 6y Python/FastAPI/Postgres at payments company"
  → skill=9, seniority=10, direction=9, domain=9

Example B (overall=6.0, borderline):
  Job: "Senior DevOps Engineer, Kubernetes/Terraform"
  Profile: "Senior Backend Engineer with Docker/AWS, no K8s production experience"
  → skill=5, seniority=10, direction=6, domain=5

Example C (overall=2.5, reject):
  Job: "Principal Engineering Manager, 10+ years leading teams"
  Profile: "Mid-level Backend Engineer, 3y experience, no management"
  → skill=3, seniority=1, direction=3, domain=4

=== OUTPUT SCHEMA (JSON only) ===

{
  "dimensions": {
    "skill_overlap":    {"score": int, "evidence": "quote from docs"},
    "seniority_fit":    {"score": int, "evidence": "..."},
    "career_direction": {"score": int, "evidence": "..."},
    "domain_relevance": {"score": int, "evidence": "..."}
  },
  "overall": float,
       // weighted: 0.35*skill + 0.30*seniority + 0.20*direction + 0.15*domain
  "one_line_reason": "<50 chars>"
}

// NOTE: do NOT emit a `decision` field. The decision is computed
//       deterministically by code from `overall` (see §8.6 finalize()).

[User]
=== JOB PROFILE ===
<job_analyses.profile_text>

=== CANDIDATE PROFILE ===
<resumes.profile_text>

Evaluate following the rubric. Return JSON only.
```

### 8.2 对应 Pydantic schema（替换旧 `MatchAnalysis`）

```python
# agent_configs/schemas.py
class RubricDimension(BaseModel):
    score: int = Field(..., ge=0, le=10)
    evidence: str

class MatchJudgment(BaseModel):
    __version__ = "v2.0.0"

    dimensions: dict[Literal[
        "skill_overlap","seniority_fit","career_direction","domain_relevance"
    ], RubricDimension]
    overall: float = Field(..., ge=0, le=10)
    one_line_reason: str = Field(..., max_length=60)
    # 注意：decision 不由 LLM 输出，由代码根据 overall 切档（§8.6）
```

**入库时**：
- `overall_score` = 代码按固定权重重算的值（**不信任 LLM 返回的 overall**，详见 §8.6），量程 [0, 10]
- `decision` = 代码按阈值切档 + 硬否决规则产出
- `dimensions` / `one_line_reason` / `llm_model` / `prompt_version` 直接落入 `job_match_recommendations` 对应字段
- **不保留 `ai_match_score` 字段**：v2 表新建无历史包袱，唯一打分列就是 `overall_score`（0-10）；前端如需展示 0-100 量程自行格式化

### 8.3 稳定性保障六件套

| 措施 | 作用 |
|------|------|
| `temperature=0`（gpt-5-mini 已默认 reasoning=low） | 消除随机抖动 |
| `response_format=json_object` / output_type=`MatchJudgment` | 强制结构化输出 |
| Rubric 硬编码在 system prompt | 量化标尺，避免主观漂移 |
| 3 个 anchor examples 固定在 system prompt | 校准打分尺度，每次用同一把尺子 |
| JD 和 Profile **同时**进同一次推理 | 保证两边用同一标准，消除不对称 |
| 版本锁定：记 `llm_model`、`prompt_version` 到 `ai_analysis` | 跨时间可复现 |

**特别重要**：
- **Anchor examples 是稳定 LLM 打分的最强手段**。
- **两路同时输入，而不是两次独立打分**。

### 8.4 回归集

维护 50 对手工标注样本 `(job_id, resume_id, expected_decision, expected_overall_range)`。
每次改 prompt 或升级模型跑一遍，观察：
- 决策一致率（应 ≥ 90%）
- 整体分布有无漂移（均值偏移 ≤ 0.3 分）

**唯一可以客观判断"LLM 判官稳不稳"的工具**。

### 8.5 对称性自检

把 J 的 profile_text 当 "candidate" 喂进去、R 的 profile_text 当 "job" 喂进去。分数应与正常方向接近（量级相符）。剧烈变化 → rubric 偏袒某一侧，改 prompt。

### 8.6 overall_score → decision 的映射规则

`decision` **不让 LLM 打**，由代码在入库时确定性计算。这样做的理由：
- LLM 在阈值边界（7.45 vs 7.55）偶尔会抖，decision 会不稳
- 阈值是产品策略，调整阈值不应该需要改 prompt、重跑 LLM
- `overall` 的加权算术本身 LLM 偶尔会算错（把 0.35 当 0.3 之类）

#### 三层计算（入库前执行）

```python
WEIGHTS = {
    "skill_overlap":    0.35,
    "seniority_fit":    0.30,
    "career_direction": 0.20,
    "domain_relevance": 0.15,
}

RECOMMEND_THRESHOLD = 7.5   # >= → recommend
BORDERLINE_THRESHOLD = 5.5  # >= → borderline，否则 reject

def finalize(judgment: MatchJudgment) -> tuple[float, str]:
    dims = {k: v.score for k, v in judgment.dimensions.items()}

    # 1) 代码重算 overall（覆盖 LLM 的 overall）
    overall = sum(dims[k] * w for k, w in WEIGHTS.items())

    # 2) 硬否决：任一关键维度 = 0 → 直接 reject
    #    seniority_fit=0 意味着职级完全不匹配（Junior → Principal）
    #    skill_overlap=0 意味着技能完全无交集
    if dims["seniority_fit"] == 0 or dims["skill_overlap"] == 0:
        return overall, "reject"

    # 3) 阈值切档
    if overall >= RECOMMEND_THRESHOLD:
        return overall, "recommend"
    if overall >= BORDERLINE_THRESHOLD:
        return overall, "borderline"
    return overall, "reject"
```

#### 阈值含义（产品策略，非算法参数）

| overall 区间 | 典型分数组合 | decision | 对用户的行为 |
|---|---|---|---|
| 9.0-10 | 四维 ≥ 9 | recommend | 入推荐列表顶部 |
| 7.5-8.9 | skill≥8, seniority≥7, 其余≥7 | recommend | 入推荐列表 |
| 5.5-7.4 | 至少一维严重短板（如 skill=5 或 seniority=3） | borderline | **不暴露给用户**，只进调试/回归集 |
| < 5.5 | 多维短板或硬否决触发 | reject | 入库但永远过滤掉 |

**阈值 7.5 的直觉**：要求 rubric 平均分 ≥ 7.5——任意单维跌破 5 都会被拉下这条线。对应用户侧"一眼觉得靠谱"。

**阈值 5.5 的直觉**：低于此说明至少一维严重不过关，出现在 UI 上会稀释推荐质量。

#### decision 与 overall_score 的分工

```
candidate pool
    │
    ├── decision     ─── 决定"是否进推荐列表"（产品开关）
    │                    前端 WHERE decision='recommend' 过滤
    │
    └── overall_score ── 决定"进了列表之后怎么排序"
                         ORDER BY overall_score DESC
```

**为什么 borderline/reject 也入库**：
- 覆盖率分析（有多少岗位每天 0 个 recommend）
- 避免重评（同一对 (user, job) 若已判 reject，下次不再送 LLM）
- 回归集可从 borderline 里挖争议样本

#### 调参时机

- 阈值 7.5 / 5.5 在阶段 1 按真实申请率调整；若"recommend 但没人申请"比例高 → 提高到 8.0
- 权重 0.35/0.30/0.20/0.15 按回归集误判模式调整；例如管理岗 skill 信号稀疏就降 skill 权重
- **每次调整都跑回归集（§8.4）**，决策一致率应维持 ≥ 90%

---

## 九、L2 粗排工程细节

### 9.1 不要设绝对阈值

```python
# 错误
if cosine_sim >= 0.70: ...

# 正确：相对排序 + 截断
candidates = sorted_by_similarity[:settings.TOP_N_VECTOR_CANDIDATES]  # 默认 30
```

原因：即使完美匹配余弦也只有 ~0.78，绝对阈值会系统性误杀。

### 9.2 "一个岗位可能匹配 0 个用户" 是正常的

L3 过完没有 `recommend` 就一个也不推。和核心诉求一致：宁推 3 条真的，不凑 20 条假的。

### 9.3 L1 过滤优先级

1. `resumes.is_draft=FALSE AND is_deleted=FALSE AND embedding IS NOT NULL AND profile_status='ok'`（硬门槛）
2. **职级差距 ≥ 3 硬拒**（详见 §9.4）—— 防止 Junior 进 Principal 岗的 top 30 挤掉真正合格的候选
3. `target_job_titles` 命中 `job_analyses.normalized_job_title` 或同族（**保留**现有 `prefilter_candidates_by_title` 作辅助，匹配不上再 fallback 到纯向量）
4. `users.preferences.job_locations ∩ seek_jobs.location_city`（若用户填了）

### 9.4 职级硬过滤规则

**数据来源**（都是已有字段，不加新列）：
- 岗位：`job_analyses.seniority`（字符串如 `'Senior'` / `'Lead'`）
- 简历：`resumes.analysis_result.total_experience_years`（int）

**映射为 1-5 档位**（代码常量，不入库）：

```python
def experience_to_tier(years: int | None) -> int | None:
    if years is None:       return None
    if years <= 2:          return 1  # Junior
    if years <= 5:          return 2  # Mid / Intermediate
    if years <= 8:          return 3  # Senior
    if years <= 12:         return 4  # Lead / Staff
    return 5                          # Principal / Manager

SENIORITY_KEYWORDS = {
    1: ["junior", "entry", "graduate", "intern"],
    2: ["mid", "intermediate"],
    3: ["senior"],
    4: ["lead", "staff", "architect"],
    5: ["principal", "director", "head", "manager"],
}

def seniority_to_tier(label: str | None) -> int | None:
    if not label: return None
    s = label.lower()
    for tier, kws in SENIORITY_KEYWORDS.items():
        if any(kw in s for kw in kws):
            return tier
    return None  # 未识别 → 不过滤
```

**过滤规则**：

| 差距 `abs(job_tier - candidate_tier)` | 动作 | 理由 |
|---|---|---|
| 0 / 1 | 通过 | 相邻级别都可能合适 |
| 2 | 通过，交 L3 打分 | 边界情况（5 年投 Mid、8 年投 Senior 都 OK），让 rubric 的 seniority_fit 扣分 |
| **≥ 3** | **硬拒** | 明显不可能（Junior 投 Principal、15 年投 Entry） |
| 任一侧为 None | 通过 | 信号缺失不拒 |

### 9.5 其他 L3 级软约束

**签证 / 远程偏好 / 薪资范围** 暂不做硬过滤，交给 L3 rubric 的 domain_relevance / career_direction 维度侧面反映。当 `users.preferences` JSONB 成熟到有这些字段且数据质量足够时，再迁为 L1 硬过滤。

---

## 十、浏览行为数据的使用（渐进式）

现有表：`user_job_views`（`first_viewed_at`/`last_viewed_at`/`view_count`）、`user_saved_jobs`。

| 用户行为量 | 做什么 |
|----------|--------|
| < 20 条 | **只埋点，不用于计算** |
| 20-100 条 | **个人化画像漂移**：浏览过的 `job_analyses.embedding` 取平均，与 `resumes.embedding` 按 0.7 : 0.3 融合，作为 L2 查询向量 |
| 100-500 条 | + 负反馈：快速关闭 / 未点击的岗位方向做反向惩罚 |
| > 500 条/用户 × 数百用户 | 考虑 LightFM / 协同过滤 |

**关键原则**：
- 个人化永远基于"这个用户自己的数据"
- 用户规模 < 1000 之前，协同过滤是伪需求

---

## 十一、成本估算

假设 500 活跃用户、每日 300 新岗位：

| 步骤 | 次数 | 单价 | 成本/日 |
|------|------|------|---------|
| L0 JD 摘要（gpt-4o-mini / gpt-5-mini） | 300 | $0.001 | $0.30 |
| L0 JD embedding（text-embedding-3-large） | 300 | $0.0005 | $0.15 |
| L0 简历摘要 + embedding | ≈ 5 新简历 | $0.01 | $0.05 |
| L3 LLM 精判（每岗位 top 30 用户） | 300 × 30 = 9000 | $0.002 | ~$18 |
| **合计** | | | **~$19/日** |

用户数 100 内实际成本 $2-5/天。

### 优化项

- L3 批处理（一次 prompt 评 5-10 组）可降 50-70%
- 热门岗位缓存 L3 结果
- 粗排分数太低的用户跳过 L3

---

## 十二、实施路线图（映射到现有代码）

### 阶段 0a：基础设施（1 人天）

| # | 任务 | 落点 |
|---|------|------|
| 1 | pgvector 扩展 + `Vector` ORM 类型 | Alembic + `app/shared/base_model.py` |
| 2 | Embedding 客户端封装 | `app/core/llm/embedding.py` |
| 3 | 新配置项 `TOP_N_VECTOR_CANDIDATES=30`，删除 `SKILL_MATCH_THRESHOLD`/`MAX_CANDIDATES_PER_JOB` | `app/core/config.py` |

### 阶段 0b：数据迁移（1 人天）

| # | 任务 | 文件 |
|---|------|------|
| 4 | **迁移 A**：`job_analyses` 加 profile_text/embedding/embedding_model/profile_version + HNSW 索引 | 新 Alembic 版本 |
| 5 | **迁移 A**：`resumes` 同样 4 列 + HNSW 索引 | 同一个迁移 |
| 6 | **迁移 B**：新建 `job_match_recommendations` + 索引 | 另一个 Alembic 版本 |
| 7 | ORM 同步：`JobAnalysis` / `Resume` 加字段；`matching/models.py` 新增 `JobMatchRecommendation`，旧 `UserJobMatch` 加 `# DEPRECATED v1` 注释 | `jobs/models.py`、`resumes/models.py`、`matching/models.py` |
| — | **迁移 C**（观察期后独立发布，不在阶段 0 范围）：`DROP TABLE user_job_matches CASCADE` + ORM 删除 | 后续 Alembic |

### 阶段 0c：L0 摘要 agent（1.5 人天）

| # | 任务 | 文件 |
|---|------|------|
| 8 | `job_profile_writer` agent（YAML + output schema） | `agent_configs/config/job_profile_writer.yaml` |
| 9 | `resume_profile_writer` agent | `agent_configs/config/resume_profile_writer.yaml` |
| 10 | `analyze_job_task` 末尾续跑 L0 生成 profile_text + embedding | `jobs/tasks.py` |
| 11 | `analyze_resume_task` 同理 | `resumes/tasks.py` |

### 阶段 0d：L1/L2/L3 流水线替换 + v1 下线（2 人天）

| # | 任务 | 文件 |
|---|------|------|
| 12 | 新 `MatchJudgment` schema，**删除** `MatchAnalysis` | `agent_configs/schemas.py` |
| 13 | **新建** `match_judger.yaml`（新 prompt + rubric + anchors + output_type=MatchJudgment），**删除** `match_analyzer.yaml` | `agent_configs/config/` |
| 14 | 重写 `matching/service.py`：**删除** v1 加权函数；新增 `vector_rank_for_job` / `vector_rank_for_user`（pgvector） | `matching/service.py` |
| 15 | 重写 `calculate_job_user_matches_task` 主体为 L1→L2→L3，写入新表 | `matching/tasks.py` |
| 16 | 重写 `match_user_recent_jobs_task` 主体 | `matching/tasks.py` |
| 17 | 重写 `analyze_match_with_ai_task`：调 `match_judger`，`update_l3()` 到新表 | `matching/tasks.py` |
| 18 | **新建** `JobMatchRecommendationRepository`（`upsert_l2` / `update_l3` / `list_recommendations_for_user`）；`UserJobMatchRepository` 标 DEPRECATED 不再使用 | `matching/repository.py` |
| 19 | **新建** `JobMatchResponse` / `JobMatchDetailResponse` 对应新表；旧 `UserJobMatchResponse*` 暂保留直到前端切完 | `jobs/schemas.py` |
| 20 | 前端推荐列表 API 切到查新表；旧 API 路由指向新表或下线 | `jobs/router.py` 等 |
| 21 | **停调度**：Celery beat 移除 `pull_unmatched_jobs` v1 调度项；保留任务名但函数体直接 return（或删除） | `core/celery_app.py`、`matching/pull.py` |

### 阶段 0e：质量保障（3 人天，可与 0d 并行）

| # | 任务 |
|---|------|
| 21 | 回归集标注（50 对 JD-Profile） |
| 22 | Prompt 调优迭代（≥ 3 轮） |
| 23 | 监控面板（决策分布、平均分、成本、粗排→精判漏召） |

**阶段 0 合计**：~8 人天（不含观察期后 drop v1 表的后续迁移）。

### 阶段 1（Month 2-3）：观察与微调

- 收集真实反馈（申请率、点赞率）
- 调整 rubric 权重（0.35 / 0.30 / 0.20 / 0.15）
- 误判案例补进回归集

### 阶段 2（Month 3+）：引入行为信号

- 基于 `user_job_views` / `user_saved_jobs` 的个人化向量漂移
- 视用户规模决定是否引入协同过滤

---

## 十三、关键决策一览

| 问题 | 决策 | 理由 |
|------|------|------|
| JD profile_text/embedding 放哪？ | `job_analyses` 加 4 列 | `seek_jobs` 只读 |
| 载体字段叫 summary 还是 profile_text？ | **`profile_text` / `profile_version`** | 这不是 JD/简历内容摘要，而是为 embedding 对齐而生的标准化画像；也避免与 `seek_jobs.abstract` / `resumes.analysis_result` 混淆 |
| 打分字段留 0-10 还是 0-100？ | **只保留 `overall_score`（0-10）**，不要 `ai_match_score` | v2 新表无历史包袱，两个单位冗余；前端要 0-100 自己格式化 |
| 结果表新建还是复用？ | **新建 `job_match_recommendations`** | v1 与 v2 列语义差异过大，复用会留永久漂移；新建更干净 |
| 旧 `user_job_matches` 表怎么办？ | v2 代码切换后 **停写**；观察期 1-2 周；独立迁移 **drop 整表** | 不做数据迁移，v1 口径无保留价值 |
| Embedding 模型？ | OpenAI text-embedding-3-large | 成本可忽略，省下的是调参时间 |
| LLM 模型？ | 沿用现有 `gpt-5-mini`（锁日期版本） | 已集成，精判够用 |
| 用户硬约束放哪？ | `users.preferences.job_locations`（已有）；签证/职级交 L3 | 避免为半成熟维度硬过滤 |
| 多简历？ | `resumes` 级 embedding，用户级取 max | 各简历独立，argmax 即推荐简历 |
| 触发方式？ | **沿用 `pull_unmatched_jobs` 岗位驱动** | 不变 |
| 向量阈值？ | **不设绝对阈值**，相对 top N=30 | 余弦上限 ~0.78，绝对阈值会误杀 |
| 行为数据何时用？ | 延后 | 规模不够协同过滤是伪需求 |

---

## 十四、风险与缓解

### 14.1 失败态与重试（L0 / L3）

流水线 3 处调 LLM：L0-J、L0-R、L3。任一失败都会阻塞下游，必须显式处理。

**状态字段**（迁移 A 同步加，除基础列之外）：

| 表 | 字段 | 取值 |
|---|---|---|
| `job_analyses` | `profile_status` TEXT DEFAULT 'pending' | `'pending'` / `'ok'` / `'failed'` |
| `job_analyses` | `profile_error` TEXT NULL | 最后一次失败原因（供人工排查） |
| `resumes` | `profile_status` TEXT DEFAULT 'pending' | 同上 |
| `resumes` | `profile_error` TEXT NULL | 同上 |
| `job_match_recommendations` | `l3_status` TEXT DEFAULT 'pending' | `'pending'` / `'ok'` / `'failed'` |
| `job_match_recommendations` | `l3_error` TEXT NULL | 同上 |

**重试策略**：Celery `max_retries=3`，退避 60s → 120s → 240s，每次失败 `retry_count++`；超限写入 `status='failed'` 并停止。

**下游门禁**：
- `pull_unmatched_jobs` 只看 `profile_status='ok'` 的 `job_analyses`
- L1 候选池只含 `resumes.profile_status='ok'`
- 前端推荐列表 `WHERE l3_status='ok' AND decision='recommend'`（pending / failed 天然不展示）

**中间态展示**：不给用户看"计算中"——L2 完成而 L3 pending/failed 的行静默隐藏，避免 UI 出现数字在变的体验。

**运维监控**：状态字段按 `status` 聚合即可作为仪表盘信号；`failed` 计数飙升 = LLM 服务异常。

### 14.2 其他风险

| 风险 | 缓解 |
|------|------|
| L0 格式抽风（字段缺失、章节错位） | output_type 强约束 + JSON 修复重试 + 兜底时 `profile_text = 原 JD 首 N 字符`（仍走 embedding，避免该行永远缺席） |
| embedding 维度与 pgvector HNSW 兼容 | **已强制 `dimensions=1536`**（HNSW 索引 2000 维上限）；若未来需回到 3072 维必须改用 IVFFlat 或 brute-force，无 HNSW |
| L3 LLM 模型升级导致打分漂移 | 锁定模型日期版本；变更前跑回归集 |
| 粗排 top 30 漏掉真正匹配 | 职级硬过滤先把跨级噪声挤出（§9.4）；回归集加入"粗排靠后但 LLM recommend"反例；监控漏召回率 |
| 成本超预期 | L3 批处理、缓存、调低 top N |
| 某类岗位（管理岗）系统性误判 | 针对类型补 anchor examples，不改主 rubric |
| Embedding 模型 / dimensions 参数变更 | 变更即相当于重算全量；用 `embedding_model` + dimensions 版本化记录，触发重算任务 |
| v1 表下线影响线上用户 | 切换时给用户 banner "匹配算法升级中"；dev/staging 先跑齐；前端读取切到新表后再停 v1 任务 |
| `pull_unmatched_jobs` 在切换窗口双跑 | 一次部署内完成：**移除 beat 调度 + v2 代码上线**；避免并行双写 |
| v1 表 drop 前有脏依赖 | 观察期内 grep `UserJobMatch` / `user_job_matches` 引用；全部清零后才发 drop 迁移 |
| `job_analyses.seniority` / `total_experience_years` 数据噪声 | §9.4 映射未识别档位返回 None → 不做硬过滤（信号缺失时让 L3 兜底） |

---

## 十五、与先前研究方案的差异

| 先前研究方案 | 本方案 | 差异原因 |
|-------------|-------|---------|
| 技能字段级匹配 + OR/AND 分组 | 整段文本 embedding + LLM | 手工规则模拟的事 embedding 已经做了 |
| 岗位类型自适应权重 | 不分类型，端到端相似度 + LLM 精判 | 自适应权重永远调不好，LLM 比加权更懂语义 |
| skill / intent / experience / level 加权求和 | 向量相似度 + LLM 精判 | 加权求和在信号稀疏场景（管理岗）必然失效 |
| bge-small-en-v1.5 | OpenAI text-embedding-3-large | 小模型省的是几十美元，损的是效果 |
| 职级乘法惩罚 | 放 L3 rubric 的 `seniority_fit` 维度 | 职级信号弱时不应直接打折 |
| LightFM / LightGBM LTR | 至少 1 年后再考虑 | 样本量不够就是不够 |

---

## 十六、一句话总结

**向量相似度找话题相关的候选人，LLM 精判决定谁真能胜任；JD 摘要/向量挂 `job_analyses`、简历挂 `resumes`；v2 结果写入新表 `job_match_recommendations`，v1 的 `user_job_matches` 与加权流水线整体停用，观察期后独立迁移 drop。靠 rubric + anchor examples + 回归集把 LLM 判官做成可验证、可复现的稳定组件。**

---

## 附录 A：新旧实现对照速查

| 关注点 | v1.0.0（现状） | v2.0.0（本方案） |
|---|---|---|
| 入口任务 | `pull_unmatched_jobs` → `calculate_job_user_matches_task` | **不变** |
| L1 | `prefilter_candidates_by_title`（title 字面） | `is_draft=F/is_deleted=F/has_embedding` + title 辅助 + 地点可选 |
| 粗排 | `calculate_skill_match_score` 加权 | **pgvector cosine**，用户级 max |
| 阈值 | `SKILL_MATCH_THRESHOLD=40`（绝对分） | **相对 top N=30** |
| 选简历 | 对每份简历跑 skill 加权取 max | cosine(job_emb, resume.embedding) argmax |
| 精排 | `match_analyzer` → `MatchAnalysis`（strengths/...） | `match_judger` → `MatchJudgment`（dimensions/decision/...） |
| 结果表 | `user_job_matches`（写） | **`job_match_recommendations`（新建写入）**；v1 表停写，观察期后 drop |
| 迁移 A | - | `job_analyses` +4 列 + HNSW 索引 / `resumes` +4 列 + HNSW 索引 |
| 迁移 B | - | `CREATE TABLE job_match_recommendations` + 索引 |
| 迁移 C（后续） | - | `DROP TABLE user_job_matches CASCADE` + 从 ORM 删 `UserJobMatch` |

## 附录 B：相关研究文档

外部研究报告位于 `D:\myDemos\jobpilot-research\`：

- `research_job_matching_algorithms.md` — 原始研究简报
- `research_output/FINAL_INTEGRATION_REPORT.md` — 多 agent 研究综合报告
- `research_output/topic_A_semantic_skill_matching.md` — 技能语义匹配
- `research_output/topic_B_job_category_matching.md` — 岗位意图向量化
- `research_output/topic_C_cold_start_strategy.md` — 冷启动策略
- `research_output/topic_D_bilateral_matching.md` — 双向匹配
- `research_output/topic_E_seniority_matching.md` — 职级匹配
- `research_output/topic_F_sparse_behavior_data.md` — 稀疏行为数据
- `research_output/topic_G_skill_dynamic_weights.md` — 技能动态权重
- `research_output/topic_H_multi_signal_fusion.md` — 多信号融合

本方案在现有 JobPilot 代码和表结构之上实现：JD profile_text/embedding 入 `job_analyses`（加 4 列），简历入 `resumes`（加 4 列），v2 结果写入**新建的** `job_match_recommendations` 表。v1 `user_job_matches` 表、`skill_match_score` 加权流水线、`MatchAnalysis` schema 与 `match_analyzer` agent **整体下线**，观察期后独立迁移 drop v1 表。
