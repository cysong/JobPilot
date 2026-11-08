# JobPilot 岗位匹配 v3 设计方案

> **版本**: v3.3
> **日期**: 2026-11-08
> **状态**: 第 1 阶段实施中
> **取代**: v1 匹配流水线（`backend/app/modules/matching/`）、[job_matching_algorithm_design.md](job_matching_algorithm_design.md)（v2，未实施）
>
> v3.3：第 1 阶段评估后调整——判定 prompt v2（A 档标准、非核心缺口不降级）、新增 `WORK_LOCATION` / `LANGUAGE` 拒绝与 `other_constraints` 提示、候选人所在国默认新西兰、岗位族 f2（拆出 `app_support`）。
>
> v3.1：合入独立评审（Fable）意见及确认结果——地点"未知不拒绝"、gateway 支持按调用指定模型、档位稳定性措施、评估标签定位、prompt 顺序、队列与重试、岗位族版本、标注只追加、新绑定回填、可观测性。

---

## 0. 背景

### 0.1 v1 的问题（2026-11-07 线上数据）

| 现象 | 数据 | 根因 |
|---|---|---|
| 分数挤在一起，无法区分 | 47 条匹配，p10–p90 = 42–58 | 技能名精确匹配 + 平均值加权 |
| 与真实投递脱节 | 555 个申请中只有 12 个有 v1 匹配；4 个面试 / Offer 全部不在 v1 结果中 | 职位名精确过滤 |
| 软技能分恒为 0、AI 复评从未成功 | 0 / 47 | 代码缺陷 |
| 不区分"有技术有经验"与"有技术无经验" | — | 没有经验维度 |

### 0.2 数据现状（2026-11-08）

| 项 | 值 |
|---|---|
| 岗位总数 / 近 30 天新增 | 21,783 / 2,237（约每月 2,100–2,200） |
| 不同职位名（规范化后） | 7,100 个；前 100 个覆盖 37% 岗位，前 300 个覆盖 50%；4,748 个只出现一次 |
| 标题含 " - " / " \| " / "/" 的岗位 | 近 30 天约 23% |
| 地点字段 | 近 30 天 18% 的岗位 `location_city` 为空（多为全国性岗位或 "Auckland, New Zealand" 这类标签）；部分岗位的 city 填成大区（如 Christchurch 的岗位 city 为 "Canterbury"） |
| JD 正文长度（去 HTML） | 平均 4,216 字符，p90 6,519 字符 |
| 简历原文长度 | 平均 7,819 字符，最长 10,886 字符 |
| 过期标记 | `is_expired = true` 全库仅 8 条；近期一半以上岗位没有 `expires_at` |
| 申请记录 | APPLIED 318、READY 137、REJECTED 92、PENDING 2、PHONE_SCREEN 1、INTERVIEWING 2、OFFER 1、FAILED 2 |
| 新岗位来源 | 外部爬虫直接写入 `seek_jobs`，后端没有"入库事件"，只能轮询 |
| 数据库 | PostgreSQL 17.4 |

---

## 1. 方案概览

```
轮询新岗位（在架、尚未归类）
  │
  ① 岗位族归类：职位名 → 岗位族（缓存；模糊职位名读部分正文）
  │
  ② 候选简历：对每个用户，取与岗位【同族】的简历；没有则取【相邻族】的简历；仍没有 → 跳过
  │
  ③ 地点硬过滤（代码）：能确定岗位城市且不在用户可接受范围、且非远程 → 拒绝；无法确定 → 未知，不拒绝
  │
  ④ 入队 job_matches（status = queued）
  │
  ⑤ LLM 判定：按发布时间从新到旧出队，出队时再检查在架；每个「岗位 × 用户」调用一次
  │     输入：指令 → 用户签证 / 安全许可状态 → 候选简历 → JD
  │     输出：签证 / 安全许可是否满足（不满足 → 拒绝 + 原因 + JD 原文）
  │           最佳简历、技术等级、经验等级、档位 A/B/C/D、档位原因
  │
  ⑥ 代码校验 → 写回 job_matches（每个「岗位 × 用户」一条）
```

**成本特征**：岗位族归类按不同职位名计费（有缓存）；LLM 判定按"通过岗位族初筛的岗位 × 用户"计费。由于每份简历属于不同岗位族，大多数岗位只会命中用户的一份简历。

---

## 2. 已确认决策

| # | 决策 |
|---|---|
| 1 | 初筛基于**岗位族（职业序列）**及其相邻族，不使用技术栈、向量 |
| 2 | 岗位族表与相邻关系由现有岗位数据整理（§4.1），维护在带版本号的 YAML 中 |
| 3 | 职位名归类**只看职位名**；模糊、无法归类的职位名**读部分正文**再归类 |
| 4 | 每份简历**只绑定一个**岗位族 |
| 5 | 候选简历**同族优先**，没有同族简历才用相邻族 |
| 6 | 同一用户多份简历匹配同一岗位，**只记录一条最佳匹配** |
| 7 | 初筛通过后，JD 与简历**直接交给 LLM 判定**，使用质量较好的模型 |
| 8 | **LLM 直接给出**技术等级、经验等级和最终档位并说明原因；不用代码推导档位 |
| 9 | 地点用岗位字段**在代码中硬过滤**，无法确定地点时视为未知、不拒绝；签证、安全许可**由 LLM 读正文判断** |
| 10 | 职级严重不符判为 **C**，不拒绝 |
| 11 | 简历内容或岗位族变更后**不重跑**已有匹配；只有岗位族被删除时才迁移引用它的数据 |
| 12 | 用户新绑定岗位族（含新用户）时，对当前在架、尚无匹配记录的岗位做一次性回填 |
| 13 | 过期判定：`expires_at` 为空时按发布 30 天，全局配置 `JOB_EXPIRY_DAYS` |
| 14 | 偏好只保留简历无法体现的信息：地点（已有）、签证状态、安全许可 |
| 15 | 管理员可修正档位；标注只追加不覆盖，用于校准与评估 |
| 16 | "投递过"（含 READY / PENDING）**只用于检验初筛召回**，不参与档位精确率 |
| 17 | v1 表 `user_job_matches` 停止使用，数据保留 |
| 18 | 模型统一经 **OpenRouter** 调用：强档 **GPT-6.1 Terra**（推理 high），轻档 **GLM-5.3 Flash**（§6.5） |

---

## 3. 结果定义

### 3.1 档位（LLM 判定与管理员标注的共同规范）

| 档位 | 名称 | 定义 |
|---|---|---|
| **A** | 强烈推荐 | 技术栈匹配，**并且**有相关的实际工作经验 |
| **B** | 可以一试 | 有相应的技术能力但缺少相关经验；或有相关经验但缺少个别核心技术 |
| **C** | 不建议 | 技术栈和经验都不匹配；或职级严重不符 |
| **D** | 不相关 | 完全不同的岗位方向（岗位族初筛的漏网之鱼） |

### 3.2 拒绝

| 原因代码 | 判定方式 | 判定时机 |
|---|---|---|
| `LOCATION` | 岗位地点可以确定，且不在用户可接受范围内，且不是远程（§5.2） | LLM 调用之前，代码判定 |
| `WORK_RIGHTS` | JD 的签证要求用户不满足 | LLM 判定（读正文 + 用户签证状态） |
| `SECURITY_CLEARANCE` | JD 的安全许可要求用户不满足 | LLM 判定（读正文 + 用户安全许可状态） |
| `WORK_LOCATION` | JD 要求在候选人所在国以外的国家现场办公，或要求居住在其他国家（含仅限某些国家居民的远程岗位） | LLM 判定（读正文 + 候选人所在国） |
| `LANGUAGE` | JD 明确要求的语言（不含编程语言、"加分项"）不在用户语言中 | LLM 判定（读正文 + 用户语言） |

- 用户未填写对应偏好时：城市不过滤（`LOCATION` 不判定）；签证 / 安全许可 / 语言在 prompt 中注明 `unknown`，LLM 不得据此拒绝。
- 候选人所在国取 `preferences.country`，未设置时默认新西兰（`MATCH_DEFAULT_COUNTRY`），因此 `WORK_LOCATION` 始终判定。
- `WORK_LOCATION` 与代码层的 `LOCATION` 是两个代码：后者有"不调用 LLM"的数据库约束。
- **其他硬性条件**（驾照、背景审查、经常出差、轮值待命等）由 LLM 列入 `other_constraints` 并附 JD 原文，只提示、不拒绝。
- 被拒绝的记录保留 LLM 给出的档位（`LOCATION` 除外），在"已拒绝"筛选中显示原因与 JD 原文。

### 3.3 展示

| 结果 | 默认展示 |
|---|---|
| A | 绿色徽标，排最前 |
| B | 黄色徽标 |
| C | 默认折叠 |
| D | 不显示（API 默认排除） |
| 拒绝 | 不在默认列表中，"已拒绝"筛选中可见 |
| 地点未知 | 档位徽标旁标注"地点未确认" |

---

## 4. 岗位族

### 4.1 岗位族定义（初版，依据线上职位名分布整理）

配置文件：`backend/app/modules/matching/config/role_families.yaml`，顶层带 `version`（当前 `f2`）。括号内为线上规范化职位名的岗位数。

| 岗位族 | 名称 | 代表职位名 | 相邻族 |
|---|---|---|---|
| `software_dev` | 软件开发 | software engineer (1075)、software developer (178)、developer (168)、full stack developer/engineer (约 300)、web developer (46)、front-end / frontend (约 90)、mobile engineer (53)、backend engineer、java / c++ / salesforce / guidewire developer、embedded software engineer、product engineer | `qa_test`、`devops_platform`、`integration`、`architecture`、`data_engineering`、`ml_ai`、`eng_management` |
| `qa_test` | 测试与质量 | test analyst (89)、test engineer (63)、quality assurance / qa engineer (100)、test automation / automation test engineer (71)、software tester、test manager | `software_dev`、`devops_platform` |
| `devops_platform` | DevOps / 平台 / 云 | devops engineer (161)、cloud engineer (128)、platform engineer (105)、site reliability engineer (83)、cloud infrastructure / cloud platform engineer | `software_dev`、`qa_test`、`infrastructure`、`security`、`architecture` |
| `infrastructure` | 系统与网络 | infrastructure engineer (82)、systems administrator (约 105)、network engineer (62)、it / ict systems engineer、database administrator、identity engineer | `devops_platform`、`security`、`it_support` |
| `it_support` | IT 支持 | service desk analyst (195)、it support engineer / technician / specialist / analyst、technical support specialist、desktop support engineer | `infrastructure`、`app_support` |
| `app_support` | 应用支持（f2 新增） | application support analyst / engineer、production support engineer、software implementation consultant、servicenow administrator、technical support engineer | `software_dev`、`it_support` |
| `data_engineering` | 数据工程 | data engineer (374)、analytics engineer (36) | `software_dev`、`data_analytics`、`ml_ai` |
| `data_analytics` | 数据分析 / BI | data analyst (163)、business intelligence analyst、data consultant | `data_engineering`、`business_analysis` |
| `ml_ai` | AI / 机器学习 | ai engineer (73)、data scientist (72)、machine learning engineer (49) | `software_dev`、`data_engineering` |
| `architecture` | 架构 | solution(s) architect (143)、enterprise architect (31)、architect | `software_dev`、`integration`、`devops_platform` |
| `integration` | 集成 | integration engineer (24)、integration developer (22) | `software_dev`、`architecture` |
| `security` | 信息安全 | security engineer、cyber security engineer、security analyst | `devops_platform`、`infrastructure` |
| `business_analysis` | 业务分析 | business analyst (431)、technical business analyst (96)、business systems analyst、systems analyst、technical analyst、product analyst | `product_delivery`、`data_analytics` |
| `product_delivery` | 产品 / 项目 / 交付 | project manager (148)、project coordinator (70)、product manager (63)、product owner (62)、service delivery manager、delivery manager、programme manager | `business_analysis`、`eng_management` |
| `eng_management` | 技术管理 | engineering manager (62)、software engineering manager、it manager、head of engineering、chief technology officer | `software_dev`、`product_delivery` |
| `ai_data_work` | AI 训练 / 标注类零工 | data science expert (45)、computer engineering expert (33) 等按小时计酬的 AI 项目岗位 | — |
| `research` | 科研 | postdoctoral researcher、masters or phd researcher | — |
| `other_engineering` | 其他工程 | electrical engineer (47)、mechanical engineer、project engineer | — |
| `other` | 其他非 IT | registered nurse、psychologist、social worker、finance business partner 等 | — |

- 相邻关系在 YAML 中双向生效（写一边即可）。
- 第 1 阶段对全部职位名归类后，按归类结果、初筛召回和抽样漏检（§8.4）复核一次。
- **f2（2026-11-08）**：从 `it_support` 拆出 `app_support`（应用支持 / 实施类岗位，此前投递有命中）；`ai_data_work` 保持孤立，不再投递此类岗位。拆分时只对 `it_support` 下非管理员来源的职位名重新归类，再按新缓存刷新岗位归类（读正文归类的岗位只在管理员固定其职位名时跟随）。

**版本与演化**：
- 修改相邻关系、新增族：`version` 升级；只影响之后的新岗位，不改已有匹配和简历绑定。
- **管理员修正**：`families set-title "TITLE" FAMILY|ambiguous` 写入 `source = admin` 的缓存行（之后不会被模型覆盖），再执行 `families refresh-jobs`。
- **删除或拆分某个族**：必须附带迁移脚本，把引用该族的 `job_title_families`、`job_role_families`（未判定的）、`resumes.role_family` 映射到新族；已判定的 `job_matches` 保留原值。

### 4.2 职位名规范化（缓存键 `title_key`）

1. 转小写，去掉首尾空白，合并连续空白，统一破折号与引号。
2. 去掉括号及方括号内的内容（多为地点、合同期）。
3. **级别与雇佣类型词只在作为修饰语时去除**：仅当该词位于另一个职位词之前或之后时去除，例如 "senior software engineer" → "software engineer"；"tech lead"、"team lead"、"lead"（单独出现）保留。级别词：senior、snr、sr、junior、jnr、jr、intermediate、mid-level、graduate、associate、staff、principal、lead；雇佣类型词：contract、contractor、fixed term、temporary、part time、full time。
4. head、director、manager、chief 等是职位本身的一部分，**不去除**。
5. **不截断** " - "、" | " 之后的内容（其中常有关键信息）。

### 4.3 职位名归类

```
title_key 在 job_title_families 中？
  ├─ 是，status = classified → 使用缓存的岗位族
  ├─ 是，status = ambiguous  → 走「读正文归类」
  └─ 否 → 进入待归类集合；批量（每次 50 个）调用 title_classifier（小模型）
          输出：每个 title_key → 岗位族 或 ambiguous；写入 job_title_families
```

**读正文归类**（仅 `ambiguous` 的岗位）：
- 输入：原始职位名 + 去 HTML 后正文前 1,500 字符 + 岗位族列表及说明。
- 输出：岗位族（必须给出）+ 一句理由。结果写入 `job_role_families`，不回写职位名缓存。
- 典型模糊职位名：engineer、consultant、analyst、automation engineer、systems engineer、support engineer、technical specialist、application specialist、quality engineer、field engineer。

**管理员修正**：后台修改某个 `title_key` 的岗位族（`source = admin`，之后不会被重新归类覆盖）。修正时同步更新该 `title_key` 下**尚未判定**的岗位（`job_role_families` 为 `pending`，或对应 `job_matches` 仍为 `queued`）；已判定的不变。

**归类器升级**：归类 prompt 或模型升级时，只对 `ambiguous` 和非 admin 的 `title_key` 重新归类，结果只影响之后的新岗位。

**一次性初始化**：对现有约 7,100 个 `title_key` 批量归类，约 150 次小模型调用。

### 4.4 简历绑定岗位族

- 字段：`resumes.role_family`，每份正式简历一个。
- **自动建议**：简历定稿时，把 `target_job_titles`（来自受控词表，即线上已出现的职位名）规范化后查缓存，取出现最多的岗位族；平票取第一个目标职位名的岗位族。
- **用户可修改**：简历页提供岗位族选择。修改后不重跑已有匹配；触发一次回填（§10.3）。
- 未绑定岗位族的简历不参与匹配。

---

## 5. 候选简历与地点过滤（LLM 调用之前）

### 5.1 候选简历

对每个新岗位 `J`（岗位族 `F`）和每个用户 `U`：

```
1. 岗位在架：未标记过期，且 (expires_at > now() 或 (expires_at 为空 且 listed_at > now() - JOB_EXPIRY_DAYS))
2. same     = U 的正式简历中 role_family = F 的简历
   adjacent = U 的正式简历中 role_family ∈ adjacent(F) 的简历
   candidates = same 非空 ? same : adjacent
   candidates 为空 → 跳过（不入库）
   candidates 超过 MATCH_MAX_CANDIDATE_RESUMES（默认 3）→ 取最近更新的 3 份
```

### 5.2 地点过滤

**岗位地点解析**（按顺序，得到一个城市集合或"未知"）：
1. `location_city` 非空 → 先经过"大区 → 城市"映射（如 Canterbury → Christchurch、Waikato → Hamilton），再作为岗位城市。
2. `location_city` 为空 → 从 `location_label` 分词，匹配城市名或大区名（同样经过映射）。
3. 仍无法确定，或标签只有国家名（如 "New Zealand"）→ **未知**。

映射表维护在 `backend/app/modules/matching/config/nz_locations.yaml`（城市、所属大区、常见别名）。

**远程判定**：`work_types_label` 或 `location_label` 中含独立词 `remote` / `work from home`；标题中仅当以 "(Remote)"、"- Remote"、"Remote -" 形式出现时才算，避免误判 "Remote Monitoring Engineer" 这类职位。

**结果**（写入 `job_matches.location_check`）：

| 情况 | `location_check` | 处理 |
|---|---|---|
| 用户未设置 `job_locations` | `not_applicable` | 正常判定 |
| 岗位远程 | `remote` | 正常判定 |
| 岗位城市在用户可接受范围内 | `matched` | 正常判定 |
| 岗位地点未知 | `unknown` | 正常判定，界面标注"地点未确认" |
| 岗位城市确定且不在范围内 | `rejected` | 入库为拒绝（`LOCATION`），不调用 LLM |

---

## 6. LLM 判定

### 6.1 输入（按此顺序拼接，便于缓存命中）

同一用户连续判定时，前三段保持不变，可以命中 provider 的前缀缓存；只有最后的 JD 每次变化。

```
[INSTRUCTIONS]           规则、档位定义、锚定示例（固定）

[CANDIDATE CONDITIONS]
work_rights: citizen | permanent_resident | work_visa | needs_sponsorship | unknown
security_clearance: holds | eligible | not_eligible | unknown
located_in: <preferences.country，缺省 New Zealand>
languages: <preferences.languages，如 English, Chinese> | unknown

[CANDIDATE RESUMES]      1–3 份（大多数情况 1 份）
resume_id, title, role_family
content: 简历 Markdown 原文

[ADDITIONAL SKILLS FROM SKILL LIBRARY]
技能库中候选简历都未出现的技能：skill_name, proficiency, 出处原文（resume_skills.extracted_from）

[JOB]
title, location_label, work_types_label, listed_at
description: 去 HTML 后的 JD 全文（列表项保留为 "- " 行）
```

城市已在调用前由代码过滤；`located_in` 只用于判断"是否要求在其他国家工作"。

### 6.2 输出（`MatchJudgment`）

```python
class Evidence(BaseModel):
    job_quote: str | None          # verbatim from the JD
    resume_quote: str | None       # verbatim from the chosen resume or skill library


class TechItem(BaseModel):
    requirement: str               # the JD requirement, verbatim
    is_core: bool                  # defines the role
    relation: Literal["same", "substitute", "missing"]
    evidence: Evidence


class WorkRightsCheck(BaseModel):
    requirement: Literal["none", "right_to_work", "pr_or_citizen", "citizen"]
    quote: str | None              # verbatim JD sentence; required unless requirement == "none"
    satisfied: bool | None         # None when the candidate status is "unknown"


class ClearanceCheck(BaseModel):
    requirement: Literal["none", "obtainable", "must_hold"]
    quote: str | None
    satisfied: bool | None


class WorkLocationCheck(BaseModel):
    requirement: Literal["none", "onsite_outside_candidate_country", "resident_outside_candidate_country"]
    country: str | None
    quote: str | None
    satisfied: bool | None


class LanguageCheck(BaseModel):
    required_languages: list[str]  # spoken/written languages the JD requires
    quote: str | None
    satisfied: bool | None         # None when the candidate languages are unknown


class OtherConstraint(BaseModel):
    requirement: str               # e.g. "full NZ driver licence"; never a rejection reason
    quote: str


class Rejection(BaseModel):
    code: Literal["WORK_RIGHTS", "SECURITY_CLEARANCE", "WORK_LOCATION", "LANGUAGE"]
    reason: str                    # one sentence
    quote: str                     # verbatim JD sentence


class MatchJudgment(BaseModel):
    decision: Literal["rated", "rejected"]
    rejection: Rejection | None    # required when decision == "rejected"
    work_rights: WorkRightsCheck
    security_clearance: ClearanceCheck
    work_location: WorkLocationCheck
    languages: LanguageCheck
    other_constraints: list[OtherConstraint]
    best_resume_id: str            # must be one of the candidate resume ids
    is_different_track: bool       # different career track -> tier D
    seniority_mismatch: bool       # severe mismatch -> tier C
    tech_level: Literal["strong", "partial", "weak"]
    tech_items: list[TechItem]     # core and must-have requirements, at most 12
    experience_level: Literal["strong", "partial", "none"]
    relevant_years: float | None   # years of relevant, dated work experience
    required_years: float | None   # minimum years stated in the JD; None if not stated
    experience_evidence: list[Evidence]
    tier: Literal["A", "B", "C", "D"]
    tier_reason: str               # 1-2 sentences referencing concrete requirements and evidence
```

- 被拒绝时仍输出档位等字段，便于了解"不受签证限制时会是什么档位"。
- 字段顺序有意安排为"先判断、后结论"，让模型先完成各项判定再给出档位。

### 6.3 Prompt 规则（`agent_configs/config/match_judge.yaml`，当前 v2）

v2 依据第 1 阶段 50 条标注调整（v1 把 13/18 个应为 A 的岗位判成 B，原因是把非核心缺口当成降级理由）：
- `is_core` 只限定义岗位的少数要求（主语言 / 平台、主框架或测试工具、主要工作类型）；具体工具、行业产品、"experience with X, Y, Z" 长列表不算核心。
- `tech_level = strong`：核心要求全部 `same` 或用过的近似替代；**非核心缺口不降低 `tech_level`**。
- 按角色判断而非逐词匹配（如 QA Lead / SDET 默认做过测试计划、回归和手工测试）。
- 兼做其他职责的岗位（QA Lead 兼开发工具、全栈之于后端岗位）年限全额计入；`relevant_years >= required_years - 2` 即为 `strong`。
- 职级严重不符：差约 4 年以上、Principal / Head / Director 岗位而候选人非 lead、或 graduate / junior 岗位而候选人 8 年以上。
- 档位：A = 技术 strong 且经验 strong；B = 技术 strong 而经验不足，或经验 strong 而技术 partial；C = 技术 weak，或技术 partial 且经验非 strong，或职级严重不符；D = 不同方向。A / B 拿不准时，招聘方会给面试就选 A。
- 替代技术补充 Cucumber / SpecFlow、Kafka / RabbitMQ、Jest / Vitest。

以下为 v1 起的基本规则：

1. **档位定义**：§3.1 原文写入 prompt。档位由 LLM 综合判断给出。
2. **D 档**：岗位与候选人的职业方向完全不同时，`is_different_track = true`，档位为 D。
3. **技术判定**：
   - `same`：同一技术，包括写法与版本差异（PostgreSQL / Postgres、React / React 18）。
   - `substitute`：同类且经验可迁移（AWS / Azure、Selenium / Playwright、Java / C#）。
   - "A, B or C" 满足其一即可；"A and B" 需全部满足。
   - 技能库补充中的技能也算具备，但证据要标明来源。
   - `is_core`：定义该岗位的技术（出现在标题中、带年限要求、在要求中排在前面或在职责中反复出现）。
4. **技术等级**：`strong` = 核心技术全部 `same`；`partial` = 核心技术有 `substitute` 或个别缺失；`weak` = 核心技术大部分缺失。
5. **经验等级**：以简历中**带起止日期的工作经历**为准，计算从事相关工作的年限。项目、课程、技能列表不计为工作经验。
   - JD 写明年限：`strong` = 做过相关工作且年限达到要求；`partial` = 做过相关工作但年限不足；`none` = 没有相关工作经历。
   - JD 未写年限（`required_years = None`）：只看相关性。`strong` = 有直接相关的工作经历；`partial` = 有部分相关的工作经历；`none` = 没有。
6. **职级严重不符**（如要求 10 年以上而候选人 3 年；Principal / Head 岗位而候选人为中级）→ `seniority_mismatch = true`，档位为 C。
7. **最佳简历**：从候选中选出最能支撑该岗位的一份，所有引用都来自这份简历或技能库。
8. **签证与安全许可**：先从 JD 中找出要求及原句，再与候选人状态比对：

   | JD 要求 | 候选人不满足的情况 |
   |---|---|
   | `citizen` | 不是 `citizen` |
   | `pr_or_citizen` | `work_visa` 或 `needs_sponsorship` |
   | `right_to_work`（"must have the right to work in NZ"） | `needs_sponsorship` |
   | 安全许可 `must_hold` | 不是 `holds` |
   | 安全许可 `obtainable` | `not_eligible` |

   另有两项（v2）：JD 要求在其他国家现场办公或居住 → `WORK_LOCATION`；JD 明确要求的语言不在候选人语言中 → `LANGUAGE`。

   不满足 → `decision = rejected` 并填写 `rejection`。候选人状态为 `unknown`、或 JD 没有明确写出要求时，不得拒绝。代码校验（§6.4）会核对引用原文，找不到原文的拒绝不成立。
9. **只依据原文**：所有 quote 必须逐字摘自 JD 或简历，不推测。
10. **锚定示例**：A、B、C、D 各一个简短示例，随 prompt 版本维护。

**稳定性设置**：判定 agent 固定 reasoning effort（high）并设置固定 `seed`（GPT-6.1 Terra 不支持 temperature）；`prompt_version` 由人工版本号加 prompt 全文的 SHA-256 前 8 位组成，任何改动都会体现在版本上。

### 6.4 代码校验

**引用核验的规范化方式**：两侧文本都去 HTML、解码实体、统一引号与破折号、去掉行首列表符号、合并空白、转小写后，做子串匹配。

| 检查 | 不通过时 |
|---|---|
| Pydantic 结构校验 | 重试（最多 2 次），仍失败则 `failed_final` |
| `best_resume_id` 必须属于候选简历 | 同上 |
| `decision` 与 `rejection` 不一致（一个有一个无） | 同上 |
| `decision = rejected` 但 `rejection.quote` 在 JD 中找不到 | 改为 `rated`，记录 `consistency_fixes`（防止凭空拒绝） |
| `decision = rejected` 但对应候选人状态为 `unknown` | 改为 `rated`，记录 |
| `work_rights.quote`、`security_clearance.quote`、`work_location.quote`、`languages.quote` 在 JD 中找不到 | 该项要求视为 `none`，记录 |
| `other_constraints` 的 quote 在 JD 中找不到 | 删除该条 |
| `tech_items`、`experience_evidence` 中的 quote 找不到 | 保留，标记 `unverified`，计入质量统计 |
| `relevant_years` 超过最佳简历工作经历时长之和（由 `analysis_result.work_experiences[].duration` 计算） | 保留，标记 `years_exceeds_history` |
| `is_different_track = true` 但档位不是 D，或 `seniority_mismatch = true` 但档位不是 C | 保留 LLM 档位，记录 `tier_flag_conflict`，计入评估报告 |

### 6.5 模型

**选型（2026-11-08 确认）**，均通过 OpenRouter（OpenAI 兼容接口）调用：

| 档位 | 模型（OpenRouter id） | 价格（$ / 百万 token，输入 / 输出） | 能力指数（AA v5） | 用于 |
|---|---|---|---|---|
| 强档 | `openai/gpt-6.1-terra`，reasoning effort = high | 1.00 / 5.00 | 42（high） | `match_judge`；并替换现用 `gpt-5`、`gpt-5-mini` 的 agent（cover_letter_writer、cover_letter_polisher、resume_tailor、resume_analyzer、reviewer） |
| 轻档 | `z-ai/glm-5.3-flash` | 0.034 / 0.083 | 28 | `title_classifier`、`job_family_reader`；并替换现用 `MiniMax-M2.5` 的 agent（job_analyzer、universal_translator） |

- 第 1 阶段评估中，`match_judge` 额外用 `openai/gpt-6.1-sol`（reasoning effort = medium，能力指数 46）跑同一数据集作为对照，确认 Terra 的判定质量足够。
- GPT-6.1 Terra 不支持 `temperature` 参数：稳定性靠固定 reasoning effort 与 `seed` 保证（§6.3）。
- OpenRouter 账户设置关闭数据收集，只路由到不保留数据的服务商（简历含个人信息）。

**接入改动**（第 1 阶段前置任务）：
- `app/core/llm/providers.py` 新增 `openrouter` provider：使用现有配置 `OPENROUTER_API_KEY`、`OPENROUTER_API_BASE`，API 模式 `chat_completions`；请求附带 `provider.require_parameters = true`，只路由到支持结构化输出的服务商。
- `AgentGateway.call(..., model_override=None, model_settings_override=None)`：按调用覆盖 agent YAML 中的 provider / model / model_settings，用于评估时切换对照模型。
- 两个模型及对照模型加入 `MODEL_PRICING`，否则成本统计为 0。
- 系统级调用（职位名归类、读正文归类）不传 `user_id`；`ai_calls.user_id` 在库中已可空，只需把 ORM 类型标注改为 `Optional[int]`。
- 评估运行在 `config` 中记录实际生效的 provider 与 model。
- 现有 agent 的模型替换随第 1 阶段一起完成；替换后用现有功能（求职信、简历定制、JD 分析、翻译）各抽查几条结果确认质量。

---

## 7. 结果存储与展示

- 每个「岗位 × 用户」一条记录（`job_matches`）：最佳简历、档位、技术 / 经验等级、原因、拒绝信息、地点检查结果、完整判定。
- 判定为 D 的也入库（API 默认排除），用于评估初筛效果。岗位族初筛未通过的不入库。
- 不重跑已有匹配；记录中保存当时的简历内容 hash、JD 内容 hash 和岗位族版本，便于追溯。
- 职位列表：档位徽标、档位原因、推荐简历；按档位筛选；"已拒绝"筛选显示拒绝原因；"地点未确认"标注；已投递的岗位通过关联 `applications` 显示投递状态。
- 职位详情：技术逐条对照（`tech_items`）、经验依据、JD 中的签证 / 安全许可原文。

---

## 8. 校准与评估

### 8.1 管理员标注

- 仅 `ADMIN` 可见，第一阶段只标注自己的匹配。
- 位置：职位卡片档位徽标的菜单、职位详情页。第 1 阶段（还没有界面时）通过评估命令导出待标注文件，填好后导入。
- 内容：正确档位（A/B/C/D）或"应拒绝"；错误原因（多选）：`FAMILY`、`TECH`、`EXPERIENCE`、`SENIORITY`、`CONSTRAINT`、`LOCATION`、`OTHER`；备注。
- 管理员也可以对没有匹配记录的岗位标注"应该匹配"，用于发现初筛漏检。
- **只追加不覆盖**：再次标注同一配对时新增一条，旧记录通过 `superseded_by` 指向新记录。每条标注都记录当时系统结果的 prompt 版本和模型。

### 8.2 评估数据集

| 组成 | 来源 | 用途 |
|---|---|---|
| 面试 / Offer 岗位（4 个） | `applications` 状态为 PHONE_SCREEN / INTERVIEWING / OFFER | 初筛召回（必须 100% 通过，且不得判为 D） |
| 投递过的岗位 | `applications` 除 FAILED 外的所有状态（含 READY、PENDING） | **只用于初筛召回**（通过率 ≥ 98%，D 占比单独报告）；不参与档位精确率 |
| 最佳简历一致性 | 投递记录的 `source_resume_id` | 系统选出的最佳简历与实际投递简历的一致率 |
| 随机岗位 | 同期未投递岗位随机抽样 300 个（固定随机种子） | 初筛过滤率、档位分布 |
| 随机岗位中被初筛过滤的部分 | 从上一项中被过滤的岗位抽 50–100 个，**也送去判定** | 发现初筛漏检（§8.4） |
| 管理员标注 | `match_labels`（有效记录） | 档位准确性的金标准 |

- 数据集冻结后带版本号；`config` 中记录当时每份简历的 `document_id` 与内容 hash，简历以后被修改时，评估仍使用冻结时的内容，保证可比。

### 8.3 统一报告（固定章节，缺数据写 N/A）

1. **运行信息**：数据集版本、prompt 版本、provider 与模型、岗位族配置版本、归类器版本
2. **岗位族归类**：各族岗位数、ambiguous 占比、读正文归类占比
3. **初筛**：面试岗位通过率（目标 100%）、投递岗位通过率（目标 ≥ 98%）、被 `LOCATION` 拒绝的投递岗位数（目标 0）、随机岗位过滤率、同族与相邻族占比、`location_check = unknown` 占比
4. **初筛漏检**：被过滤但判定为 A/B 的岗位比例与清单
5. **档位分布**：全部、随机岗位、投递岗位分别的 A/B/C/D/拒绝分布
6. **稳定性**：同一数据集跑两次的档位一致率；`tier_flag_conflict` 数量
7. **与标注一致性**：混淆矩阵、A 精确率、A+B 召回率、跨两档以上错判率；按错误原因统计
8. **最佳简历一致率**
9. **校验统计**：`consistency_fixes`、`unverified` 引用率、`years_exceeds_history`
10. **与基线对比**：指标变化、档位变化的配对清单
11. **错判样本**：岗位、系统结果、标注、原因
12. **成本**：归类与判定的调用次数、token、费用

命令：

```bash
# All LLM-backed commands are dry runs unless --yes is given.
uv run python -m app.modules.matching.cli families classify-titles --all --yes   # one-off title cache warm-up
uv run python -m app.modules.matching.cli families init --days 30 --yes          # classify live jobs
uv run python -m app.modules.matching.cli resumes suggest --user <id> [--apply]
uv run python -m app.modules.matching.cli resumes set <resume_id> <family>
uv run python -m app.modules.matching.cli dataset create --name main --user <id> --random 300 --filtered-sample 80 --yes
uv run python -m app.modules.matching.cli run --dataset main@v1 [--model <model>] [--repeat 2] [--baseline <run>] --yes
uv run python -m app.modules.matching.cli report <run_id>
uv run python -m app.modules.matching.cli compare <run_a> <run_b>
uv run python -m app.modules.matching.cli labels export --run <run_id> --limit 50
uv run python -m app.modules.matching.cli labels import --file <csv> --labeled-by <user_id> --run <run_id>
```

报告写入 `backend/reports/matching/<run_id>.md`（已加入 `.gitignore`，含个人求职数据），同时保存在 `match_eval_runs.report_md`。

评估运行不写入线上 `job_matches`。

### 8.4 初筛漏检的发现方式

1. 评估数据集中被过滤的随机岗位抽样判定（§8.2）。
2. 管理员对无匹配记录的岗位标注"应该匹配"（§8.1）。
3. 两者发现的漏检，用于调整相邻关系或修正职位名归类。

---

## 9. 数据库设计

### 9.1 变更总览

| # | 对象 | 变更 | 阶段 |
|---|---|---|---|
| 1 | `job_title_families` | 新建：职位名 → 岗位族缓存 | 1 |
| 2 | `job_role_families` | 新建：每个岗位的岗位族 | 1 |
| 3 | `resumes` | 新增 `role_family`、`role_family_source`、`role_family_version` 三列 | 1 |
| 4 | `job_matches` | 新建：匹配结果与判定队列 | 1 |
| 5 | `match_labels` | 新建：管理员标注 | 1 |
| 6 | `match_eval_datasets` / `match_eval_items` / `match_eval_runs` / `match_eval_predictions` | 新建：评估 | 1 |
| 7 | `users.preferences` | 新增 `work_rights`、`security_clearance` 两个键（JSONB，无迁移） | 2 |
| 8 | `user_job_matches`（v1，47 条） | 停止读写，数据保留 | 2 |

**不改动**：`seek_jobs`（只读）、`job_analyses`、`documents`、`user_skills`、`resume_skills`、`applications`、`user_job_views`、`ai_calls`（`user_id` 已可空）。

约定：主键沿用 `VARCHAR(255)` 字符串 id（`generate_id(prefix)`）；时间为 `TIMESTAMPTZ`；新表 JSON 字段使用 `JSONB`。档位列（`tier`、`predicted_tier`）实现为 `VARCHAR(1)` 而非 `CHAR(1)`，取值由 CHECK 约束限定。所有迁移只新建表或新增可空列，均可 `downgrade`。

迁移：`alembic/versions/20261108_1200_ce72214e3bd7_add_matching_v3_tables.py`（第 1 阶段一次性包含 §9.1 #1–#6）。验证脚本 `scripts/verify_matching_v3_migration.py` 在本地临时库上执行 upgrade → 与 ORM 元数据比对 → downgrade → 再 upgrade。

### 9.2 `job_title_families`

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | `VARCHAR(255)` | 否 | | 主键，`jtf_` 前缀 |
| `title_key` | `VARCHAR(500)` | 否 | | 规范化职位名（§4.2） |
| `example_title` | `VARCHAR(500)` | 否 | | 首次出现时的原始职位名 |
| `status` | `VARCHAR(16)` | 否 | | `classified` / `ambiguous` |
| `role_family` | `VARCHAR(32)` | 是 | | `status = classified` 时必填 |
| `source` | `VARCHAR(16)` | 否 | | `llm` / `admin` |
| `families_version` | `VARCHAR(16)` | 否 | | 归类时的岗位族配置版本 |
| `classifier_version` | `VARCHAR(32)` | 否 | | 归类 prompt 版本 |
| `model` | `VARCHAR(64)` | 是 | | `source = llm` 时的模型 |
| `updated_by` | `INTEGER` | 是 | | FK → `users.id` `ON DELETE SET NULL`；管理员修正人 |
| `created_at` | `TIMESTAMPTZ` | 否 | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | 否 | `now()` | |

| 约束 / 索引 | 定义 |
|---|---|
| `uq_job_title_families_key` | `UNIQUE (title_key)` |
| `ck_job_title_families_status` | `CHECK (status IN ('classified','ambiguous'))` |
| `ck_job_title_families_family` | `CHECK (status <> 'classified' OR role_family IS NOT NULL)` |
| `ix_job_title_families_family` | `(role_family)` |

### 9.3 `job_role_families`

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `job_id` | `INTEGER` | 否 | | 主键；FK → `seek_jobs.id` `ON DELETE CASCADE` |
| `title_key` | `VARCHAR(500)` | 否 | | |
| `status` | `VARCHAR(16)` | 否 | `'pending'` | `pending` / `classified` / `failed` |
| `role_family` | `VARCHAR(32)` | 是 | | 归类完成前为空 |
| `method` | `VARCHAR(16)` | 是 | | `title_cache` / `jd_read`；归类完成后填写 |
| `families_version` | `VARCHAR(16)` | 是 | | |
| `reason` | `TEXT` | 是 | | `jd_read` 时 LLM 的一句理由 |
| `ai_call_id` | `VARCHAR(255)` | 是 | | `jd_read` 时关联 `ai_calls` |
| `attempts` | `SMALLINT` | 否 | `0` | |
| `error` | `TEXT` | 是 | | |
| `created_at` | `TIMESTAMPTZ` | 否 | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | 否 | `now()` | |

| 约束 / 索引 | 定义 |
|---|---|
| `ck_job_role_families_status` | `CHECK (status IN ('pending','classified','failed'))` |
| `ix_job_role_families_family` | `(role_family) WHERE status = 'classified'` |
| `ix_job_role_families_title_key` | `(title_key)` （管理员修正时更新未判定岗位） |
| `ix_job_role_families_pending` | `(status, created_at) WHERE status = 'pending'` |

### 9.4 `resumes` 新增列

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `role_family` | `VARCHAR(32)` | 是 | `NULL` | 绑定的岗位族；为空时不参与匹配 |
| `role_family_source` | `VARCHAR(8)` | 是 | `NULL` | `auto` / `user` |
| `role_family_version` | `VARCHAR(16)` | 是 | `NULL` | 绑定时的岗位族配置版本 |

索引：`ix_resumes_user_family (user_id, role_family) WHERE is_draft = false AND is_deleted = false`。

### 9.5 `job_matches`

每个「岗位 × 用户」一条，同时作为判定队列。

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | `VARCHAR(255)` | 否 | | 主键，`jm_` 前缀 |
| `user_id` | `INTEGER` | 否 | | FK → `users.id` `ON DELETE CASCADE` |
| `job_id` | `INTEGER` | 否 | | FK → `seek_jobs.id` `ON DELETE CASCADE` |
| `status` | `VARCHAR(20)` | 否 | | `queued` / `rated` / `rejected` / `failed_retryable` / `failed_final` / `skipped_expired` |
| `origin` | `VARCHAR(16)` | 否 | | `new_job` / `backfill` |
| `job_family` | `VARCHAR(32)` | 否 | | 入队时岗位的岗位族 |
| `families_version` | `VARCHAR(16)` | 否 | | |
| `family_relation` | `VARCHAR(8)` | 否 | | `same` / `adjacent` |
| `candidate_resume_ids` | `JSONB` | 否 | `'[]'` | 送入 LLM 的候选简历 |
| `location_check` | `VARCHAR(16)` | 否 | | `not_applicable` / `remote` / `matched` / `unknown` / `rejected` |
| `job_listed_at` | `TIMESTAMPTZ` | 是 | | 冗余自 `seek_jobs.listed_at`，用于出队排序 |
| `job_content_hash` | `CHAR(64)` | 是 | | 判定时 JD 文本的 SHA-256 |
| `resume_id` | `VARCHAR(255)` | 是 | | 最佳简历；FK → `resumes.id`（简历为软删除，不级联） |
| `resume_content_hash` | `CHAR(64)` | 是 | | 判定时最佳简历内容的 SHA-256 |
| `tier` | `CHAR(1)` | 是 | | `A`–`D` |
| `tier_reason` | `TEXT` | 是 | | |
| `tech_level` | `VARCHAR(8)` | 是 | | `strong` / `partial` / `weak` |
| `experience_level` | `VARCHAR(8)` | 是 | | `strong` / `partial` / `none` |
| `reject_code` | `VARCHAR(24)` | 是 | | `LOCATION` / `WORK_RIGHTS` / `SECURITY_CLEARANCE` / `WORK_LOCATION` / `LANGUAGE` |
| `reject_reason` | `TEXT` | 是 | | |
| `reject_quote` | `TEXT` | 是 | | JD 原文引用 |
| `judgment` | `JSONB` | 是 | | 完整的 `MatchJudgment`（校验后） |
| `validation` | `JSONB` | 否 | `'{}'` | 校验统计 |
| `model` | `VARCHAR(64)` | 是 | | |
| `prompt_version` | `VARCHAR(32)` | 是 | | |
| `ai_call_id` | `VARCHAR(255)` | 是 | | 关联 `ai_calls` |
| `attempts` | `SMALLINT` | 否 | `0` | |
| `next_attempt_at` | `TIMESTAMPTZ` | 是 | | 可重试失败的下次处理时间 |
| `error` | `TEXT` | 是 | | |
| `queued_at` | `TIMESTAMPTZ` | 否 | `now()` | |
| `judged_at` | `TIMESTAMPTZ` | 是 | | |
| `created_at` | `TIMESTAMPTZ` | 否 | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | 否 | `now()` | |

| 约束 / 索引 | 定义 | 用途 |
|---|---|---|
| `uq_job_matches_user_job` | `UNIQUE (user_id, job_id)` | 每个用户每个岗位一条 |
| `ck_job_matches_status` | `CHECK (status IN ('queued','rated','rejected','failed_retryable','failed_final','skipped_expired'))` | |
| `ck_job_matches_tier` | `CHECK (tier IS NULL OR tier IN ('A','B','C','D'))` | |
| `ck_job_matches_rated` | `CHECK (status <> 'rated' OR (tier IS NOT NULL AND resume_id IS NOT NULL))` | 判定成功必须有档位与简历 |
| `ck_job_matches_rejected` | `CHECK (status <> 'rejected' OR reject_code IS NOT NULL)` | 拒绝必须有原因 |
| `ck_job_matches_location_reject` | `CHECK (reject_code IS DISTINCT FROM 'LOCATION' OR (ai_call_id IS NULL AND location_check = 'rejected'))` | 地点拒绝不调用 LLM |
| `ix_job_matches_listing` | `(user_id, status, tier)` | 职位列表 |
| `ix_job_matches_queue` | `(job_listed_at DESC) WHERE status = 'queued'` | 出队（新岗位优先） |
| `ix_job_matches_retry` | `(next_attempt_at) WHERE status = 'failed_retryable'` | 重试 |
| `ix_job_matches_job` | `(job_id)` | |

### 9.6 `match_labels`

只追加，不覆盖。

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | `VARCHAR(255)` | 否 | | 主键，`ml_` 前缀 |
| `user_id` | `INTEGER` | 否 | | 被标注配对的用户；FK → `users.id` `ON DELETE CASCADE` |
| `job_id` | `INTEGER` | 否 | | FK → `seek_jobs.id` `ON DELETE CASCADE` |
| `job_match_id` | `VARCHAR(255)` | 是 | | FK → `job_matches.id` `ON DELETE SET NULL`；无匹配记录时为空 |
| `label` | `VARCHAR(16)` | 否 | | `A` / `B` / `C` / `D` / `REJECT` |
| `reason_tags` | `JSONB` | 否 | `'[]'` | `FAMILY` / `TECH` / `EXPERIENCE` / `SENIORITY` / `CONSTRAINT` / `LOCATION` / `OTHER` |
| `note` | `TEXT` | 是 | | |
| `source` | `VARCHAR(16)` | 否 | | `ui` / `import` |
| `labeled_by` | `INTEGER` | 否 | | FK → `users.id` |
| `predicted_status` | `VARCHAR(20)` | 是 | | 标注时 `job_matches.status` |
| `predicted_tier` | `CHAR(1)` | 是 | | 标注时系统档位 |
| `predicted_prompt_version` | `VARCHAR(32)` | 是 | | |
| `predicted_model` | `VARCHAR(64)` | 是 | | |
| `predicted_snapshot` | `JSONB` | 是 | | 标注时 `judgment` 快照 |
| `superseded_by` | `VARCHAR(255)` | 是 | | FK → `match_labels.id`；被新标注取代时填写 |
| `created_at` | `TIMESTAMPTZ` | 否 | `now()` | |

| 约束 / 索引 | 定义 |
|---|---|
| `ck_match_labels_label` | `CHECK (label IN ('A','B','C','D','REJECT'))` |
| `ix_match_labels_current` | `(user_id, job_id) WHERE superseded_by IS NULL` （每个配对的当前有效标注） |

### 9.7 评估表

**`match_eval_datasets`**

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `id` | `VARCHAR(255)` | 否 | 主键，`med_` 前缀 |
| `name` | `VARCHAR(64)` | 否 | 如 `main` |
| `version` | `INTEGER` | 否 | 从 1 递增；`UNIQUE (name, version)` |
| `config` | `JSONB` | 否 | 构建参数：用户、随机样本数、抽样数、随机种子、时间范围；每份简历的 `document_id`、内容 hash 与当时的 `role_family` |
| `item_count` | `INTEGER` | 否 | |
| `created_by` | `INTEGER` | 是 | FK → `users.id` |
| `created_at` | `TIMESTAMPTZ` | 否 | 默认 `now()` |

**`match_eval_items`**（主键 `(dataset_id, user_id, job_id)`）

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `dataset_id` | `VARCHAR(255)` | 否 | FK → `match_eval_datasets.id` `ON DELETE CASCADE` |
| `user_id` | `INTEGER` | 否 | |
| `job_id` | `INTEGER` | 否 | |
| `item_kind` | `VARCHAR(20)` | 否 | `interviewed` / `applied` / `random` / `random_filtered` / `labeled` |
| `label` | `VARCHAR(16)` | 是 | 有效管理员标注（冻结时复制） |
| `applied_resume_id` | `VARCHAR(255)` | 是 | 投递时使用的简历（`source_resume_id`） |
| `source_id` | `VARCHAR(255)` | 是 | `applications.id` 或 `match_labels.id` |

**`match_eval_runs`**

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `id` | `VARCHAR(255)` | 否 | 主键，`mer_` 前缀 |
| `dataset_id` | `VARCHAR(255)` | 否 | FK → `match_eval_datasets.id` |
| `config` | `JSONB` | 否 | 实际生效的 provider、模型、prompt 版本、岗位族配置版本、归类器版本、重复次数 |
| `baseline_run_id` | `VARCHAR(255)` | 是 | FK → `match_eval_runs.id` |
| `status` | `VARCHAR(16)` | 否 | `running` / `succeeded` / `failed` |
| `metrics` | `JSONB` | 是 | 报告中的结构化指标 |
| `report_md` | `TEXT` | 是 | 统一格式报告 |
| `cost` | `JSONB` | 是 | 调用次数、token、费用 |
| `error` | `TEXT` | 是 | |
| `started_at` | `TIMESTAMPTZ` | 否 | 默认 `now()` |
| `finished_at` | `TIMESTAMPTZ` | 是 | |

**`match_eval_predictions`**（主键 `(run_id, repeat_index, user_id, job_id)`）

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `run_id` | `VARCHAR(255)` | 否 | FK → `match_eval_runs.id` `ON DELETE CASCADE` |
| `repeat_index` | `SMALLINT` | 否 | 稳定性检查时第几次运行，默认 0 |
| `user_id` | `INTEGER` | 否 | |
| `job_id` | `INTEGER` | 否 | |
| `prefilter` | `VARCHAR(20)` | 否 | `same` / `adjacent` / `filtered` / `location_rejected` |
| `location_check` | `VARCHAR(16)` | 是 | |
| `status` | `VARCHAR(20)` | 是 | 同 `job_matches.status` |
| `tier` | `CHAR(1)` | 是 | |
| `reject_code` | `VARCHAR(24)` | 是 | |
| `resume_id` | `VARCHAR(255)` | 是 | 最佳简历 |
| `judgment` | `JSONB` | 是 | |

### 9.8 `users.preferences` 新增键

| 键 | 取值 | 缺省 |
|---|---|---|
| `work_rights` | `citizen` / `permanent_resident` / `work_visa` / `needs_sponsorship` | `null`，不判定 |
| `security_clearance` | `holds` / `eligible` / `not_eligible` | `null`，不判定 |
| `country` | 候选人所在国家 | `null`，按 `MATCH_DEFAULT_COUNTRY`（New Zealand） |
| `languages` | 可工作语言列表，如 `["English", "Chinese"]` | `null`，不判定 |

- 由 `UserPreferences` Pydantic schema 校验，无数据库迁移。
- 用户未填写 `work_rights` 时，设置页用简历分析结果中的 `work_right` 作为建议值预填，以用户确认后的值为准。

### 9.9 新增配置项（`app/core/config.py`）

| 配置 | 默认 | 说明 |
|---|---|---|
| `JOB_EXPIRY_DAYS` | `30` | `expires_at` 为空时的在架天数；职位列表与匹配共用 |
| `MATCH_JUDGE_MODEL` | `openai/gpt-6.1-terra` | 判定模型（经 `model_override` 生效） |
| `MATCH_JUDGE_PROMPT_VERSION` | `v2` | |
| `MATCH_DEFAULT_COUNTRY` | `New Zealand` | 用户未设置 `country` 时的所在国 |
| `TITLE_CLASSIFIER_MODEL` | `z-ai/glm-5.3-flash` | 职位名归类与读正文归类模型 |
| `MATCH_MAX_CANDIDATE_RESUMES` | `3` | 每次判定的候选简历上限 |
| `MATCH_DAILY_LLM_LIMIT_PER_USER` | `200` | 每用户每日判定调用上限 |
| `MATCH_JUDGE_CONCURRENCY` | `4` | 判定并发数 |
| `MATCH_JUDGE_BATCH_SIZE` | `40` | 每轮出队数量 |
| `MATCH_RETRY_BACKOFF_MINUTES` | `[5, 30, 180]` | 可重试失败的退避间隔 |

### 9.10 容量

- `job_matches` 每条约 3–5 KB（主要是 `judgment`），按每月约 1,000 条估算，每月约 5 MB。
- `job_role_families` 每个岗位一条，每月约 2,200 条，体积很小。

---

## 10. 任务、队列与回填

### 10.1 定时任务（Celery beat）

| 任务 | 周期 | 内容 |
|---|---|---|
| `discover_new_jobs` | 5 分钟 | 查询在架且 `job_role_families` 中没有记录的岗位（按 `listed_at` 从新到旧，每轮上限 500），写入 `pending` |
| `classify_pending_titles` | 5 分钟 | 批量归类新的 `title_key`；对缓存命中的岗位直接完成归类；`ambiguous` 的岗位做读正文归类；归类完成后计算候选简历与地点检查，写入 `job_matches`（`queued` 或 `LOCATION` 拒绝） |
| `judge_queued_matches` | 2 分钟 | 按 `job_listed_at DESC` 出队 `MATCH_JUDGE_BATCH_SIZE` 条，并发 `MATCH_JUDGE_CONCURRENCY`；出队时再检查在架（已过期 → `skipped_expired`）；遵守每用户每日上限；同时处理到期的 `failed_retryable` |

- 判定任务使用 `AsyncBaseTask` 批处理，以 `job_matches` 本身作为任务账本，不为每条判定写 `task_executions`。新增两个 `TaskType` 供批任务记录运行情况。
- 每日上限用尽时，剩余条目保持 `queued`，次日继续；岗位如果在此期间过期，出队时记为 `skipped_expired`。
- v1 的 `pull_unmatched_jobs`、`calculate_job_user_matches_task`、`match_user_recent_jobs_task`、`analyze_match_with_ai_task` 删除。

### 10.2 失败与重试

| 失败类型 | 状态 | 处理 |
|---|---|---|
| 超时、限流、provider 5xx | `failed_retryable` | 按 `MATCH_RETRY_BACKOFF_MINUTES` 设置 `next_attempt_at`；超过次数转 `failed_final` |
| 结构校验多次失败、候选简历不合法 | `failed_final` | 记录 `error`，计入监控 |

### 10.3 回填（新用户 / 新绑定岗位族）

- 触发：简历首次绑定岗位族，或用户修改简历的岗位族。
- 范围：当前在架、且该用户**尚无** `job_matches` 记录的岗位，按 §5 计算候选简历后入队（`origin = backfill`）。
- 已有记录的岗位不重跑。回填同样受每用户每日上限约束，并按发布时间从新到旧处理。

### 10.4 可观测性（Prometheus / Grafana）

| 指标 | 说明 |
|---|---|
| `jobpilot_match_queue_depth` / `jobpilot_match_queue_oldest_age_seconds` | 队列深度、最老一条的等待时长 |
| `jobpilot_match_judge_total{outcome}` | 判定结果：rated / rejected / failed_retryable / failed_final / skipped_expired |
| `jobpilot_match_judge_duration_seconds` | 判定耗时 |
| `jobpilot_match_tier_total{tier}` | 每日各档位数量，用于发现漂移（A 占比突变或为 0 时告警） |
| `jobpilot_match_validation_total{kind}` | `consistency_fixes`、`unverified`、`tier_flag_conflict` 等校验事件 |
| `jobpilot_title_classify_total{outcome}` | 职位名归类：classified / ambiguous / jd_read / failed |
| LLM 费用 | 复用现有 `jobpilot_llm_*` 指标，按 agent 统计 |

告警：队列最老一条超过 24 小时；`failed_final` 占比超过 5%；当日 A 档为 0 且判定数大于 20。

---

## 11. 代码结构

```
backend/app/modules/matching/
├── config/
│   ├── role_families.yaml        # version, families, labels, adjacency
│   └── nz_locations.yaml         # preference cities, aliases, regions
├── families/
│   ├── normalize.py              # title_key normalization (pure)
│   ├── registry.py               # load YAML, adjacency lookup (pure)
│   ├── classifier.py             # batch title classification + JD-read classification
│   ├── resume_binding.py         # suggest / bind a family per resume
│   └── models.py                 # job_title_families, job_role_families
├── judge/
│   ├── input_builder.py          # prompt sections in cache-friendly order, work history years (pure)
│   ├── validator.py              # schema, quote checks, rejection checks, flags (pure)
│   └── service.py                # load user/job context, plan_match, judge_pair
├── labels/
│   ├── models.py                 # match_labels (append-only)
│   └── csv_io.py                 # labeling sheet export / import
├── evaluation/
│   ├── models.py                 # datasets, items, runs, predictions
│   ├── dataset.py                # build and freeze datasets
│   ├── runner.py                 # run a dataset, store predictions and report
│   ├── metrics.py                # metrics and run comparison (pure)
│   └── report.py                 # unified markdown report (pure)
├── location.py                   # location resolution, remote detection (pure)
├── prefilter.py                  # active-job rule, candidate resumes (pure)
├── text.py                       # HTML to text, quote normalization (pure)
├── cli.py                        # stage 1 command line
└── models.py                     # job_matches (v3) + user_job_matches (v1, deprecated)

backend/app/core/llm/             # openrouter provider, model_override, usage in context
backend/agent_configs/config/     # title_classifier, job_family_reader, match_judge
backend/scripts/verify_matching_v3_migration.py
```

纯函数模块的单元测试不依赖数据库和 LLM；数据库相关测试在设置 `MATCHING_TEST_DATABASE_URL`（本地临时 Postgres）时运行，LLM 用 mock。

---

## 12. 实施阶段

### 第 1 阶段：归类、判定与离线评估

| 范围 | 内容 |
|---|---|
| 前置 | 新增 `openrouter` provider；gateway 支持 `model_override`；模型加入 `MODEL_PRICING`；现有 agent 切换到 GPT-6.1 Terra / GLM-5.3 Flash |
| 数据库 | §9.1 #1–#6 |
| 岗位族 | 两个 YAML、规范化、批量归类、读正文归类；对现有约 7,100 个职位名一次性归类 |
| 简历 | 为现有正式简历自动建议岗位族，由用户确认 |
| 判定 | `match_judge` prompt、输入构建、校验、地点过滤 |
| 评估 | 冻结 `main@v1`；`run` / `compare` / 稳定性检查；标注导出与导入；统一报告 |

**验收（以报告为准）**：
1. 面试岗位初筛通过率 100% 且无 D；投递岗位通过率 ≥ 98%；被 `LOCATION` 拒绝的投递岗位为 0
2. 被过滤随机岗位的抽样中，判为 A/B 的比例可接受（逐条分析后调整相邻关系或归类）
3. GPT-6.1 Terra 与对照模型 GPT-6.1 Sol：你对各约 50 条结果的标注一致率、两次运行的档位一致率、随机岗位的档位分布（不出现 v1 式集中）；Terra 质量不足时再讨论换模型
4. 实际费用与估算一致

### 第 2 阶段：上线与管理员标注

| 范围 | 内容 |
|---|---|
| 数据库 | §9.1 #7–#8 |
| 后端 | 三个定时任务、队列与重试、回填；匹配结果 API（默认排除 D）；标签 API；停用 v1；监控指标与告警 |
| 前端 | 职位卡片档位徽标与原因；按档位筛选；"已拒绝"筛选；"地点未确认"标注；详情页技术对照与经验依据；简历页岗位族选择；偏好设置新增签证与安全许可（预填建议值）；管理员标注界面；后台职位名岗位族修正 |

**验收**：新岗位在一小时内得到结果；标注正确入库且只追加；Grafana 上队列、失败率、档位分布、费用正常。

### 第 3 阶段：基于数据的优化

| 范围 | 内容 |
|---|---|
| 评估 | 用管理员标注生成 `main@v2`；对比 prompt 版本与模型 |
| 后台 | Matching Quality 页面：查看报告、指标趋势、错判列表 |

**验收**：新的 prompt 或模型在 `main@v1` 与 `main@v2` 上指标都不退步、且稳定性不下降，才切换上线。

---

## 13. 成本估算（1 个用户、4 份简历）

| 项 | 估算 |
|---|---|
| 职位名归类 | 一次性约 150 次小模型调用；之后每月新职位名几百个，费用可忽略 |
| 读正文归类 | 模糊职位名的岗位，每月约数百次小模型调用 |
| 判定调用 | 约每月 1,000 次。大多数岗位只命中一份简历，每次输入约 4,700 token（指令约 1,000 + 简历约 2,000 + JD 约 1,100 + 其他）；同时命中多份简历时按每份约 2,000 token 递增。输出约 1,600 token（含推理） |
| 前缀缓存 | 指令、用户条件、简历位于 prompt 前部，同一用户连续判定时可命中缓存，降低输入费用 |
| 判定费用 | GPT-6.1 Terra（high）约 $13–20 / 月（含推理 token 的粗估，第 1 阶段实测） |
| 归类费用 | GLM-5.3 Flash 单价极低，一次性初始化与日常归类合计每月不到 $1 |

---

## 14. 风险与对策

| 风险 | 对策 |
|---|---|
| 岗位族初筛漏掉相关岗位 | 投递 / 面试召回验收；被过滤岗位抽样判定；管理员标注"应该匹配"；调整相邻关系或归类 |
| 泛化职位名归类不准 | 标为 ambiguous，读正文归类 |
| 地点数据不规整导致误杀 | 无法确定时视为未知；大区 → 城市映射；验收要求投递岗位不被地点拒绝 |
| LLM 档位不稳定 | 档位定义 + 锚定示例；固定 reasoning effort 与 seed；先判断后结论的字段顺序；稳定性指标作为切换门槛；档位漂移告警 |
| LLM 引用不实或凭空拒绝 | 代码核验引用；拒绝原句找不到或候选人状态未知时拒绝不生效 |
| 队列积压导致岗位过期 | 新岗位优先出队；出队时检查在架；队列年龄告警 |
| 费用随用户数增长 | 同族优先；每用户每日上限；前缀缓存 |
| 岗位族配置变更导致数据失效 | 版本号；删除 / 拆分族时必须附迁移脚本 |
