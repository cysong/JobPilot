# Job与用户匹配度设计方案

## 1. 功能概述

### 1.1 业务需求

实现Job与用户的智能匹配功能，帮助用户快速发现适合的职位，并提供简历定制建议。

**核心流程:**
1. 定时任务自动计算新job与所有用户的匹配度
2. 基于用户技能库(user_skills)进行初步匹配
3. 为高匹配度用户选择最佳简历
4. 使用AI深度分析并提供定制建议

### 1.2 技术选型

- **算法匹配**: 纯Python算法，零AI成本
- **AI分析**: OpenAI GPT-4o-mini (仅用于高匹配度场景)
- **任务队列**: Celery (复用现有工作流框架)
- **数据存储**: PostgreSQL (新增 `user_job_matches` 表)

### 重要
下文如有不一致的以这里为准
- 定时任务执行的时候需要排重，在workflow表根据 job_analysis_id排除已经匹配过的job和user
- 定时任务不要直接执行，而是结合目前的workflow架构生成任务并提交到任务队列
- 任务触发可能不止一种方式，一种是定时扫描job_analysis表，另一种方式是当用户定稿了一个新的简历，更新目前的简历分析任务工作流增加一个匹配分析任务，依赖于简历分析任务（但是注意如果匹配分析结果已经存在直接更新）
- 简历匹配算法直接使用技能算法，简单计算匹配度最高的简历作为推荐简历

---

## 2. 匹配流程设计

### 2.1 整体流程图

```
┌─────────────────────────────────────────────────────────────────┐
│  定时任务触发 (每小时)                                             │
│  扫描: job_analyses 表中新分析的job                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段0: 岗位名称预筛选 (数据库查询) ⚡ 性能优化                     │
│                                                                  │
│  使用数据库JSON查询快速筛选候选用户:                              │
│  - job_analysis.normalized_job_title                            │
│  - resume.analysis_result.target_job_titles                     │
│  - SQL: JSON_CONTAINS 精确匹配                                  │
│                                                                  │
│  筛选结果: 仅保留岗位名称匹配的用户                               │
│  性能提升: 过滤掉80%不相关用户，减少后续计算量                    │
└────────────────────────┬────────────────────────────────────────┘
                         │ 岗位名称匹配
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段1: Job ↔ User 技能库匹配 (算法)                              │
│                                                                  │
│  仅对通过阶段0的候选用户进行技能匹配:                             │
│  - 读取 user_skills 表 (包含手动添加的技能)                       │
│  - 与 job_analysis 的技能要求进行匹配                             │
│  - 计算匹配度 (基础技能匹配算法)                                  │
│  - 存储到 user_job_matches 表                                    │
│                                                                  │
│  筛选条件: skill_match_score ≥ 40%（可配置）                      │
└────────────────────────┬────────────────────────────────────────┘
                         │ 匹配度 ≥ 40%
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段2: 选择最佳匹配简历 (算法)                                    │
│                                                                  │
│  对于匹配度 ≥ 40% 的 (user, job) 组合:                            │
│  - 获取该用户所有正式简历 (is_draft=False)                        │
│  - 逐个计算简历与job的匹配度:                                      │
│    * 技能匹配 (从 AnalyzedResume.technical_skills)              │         *   与job_analysis的required_skills和job_analysi.prefered_skills     进进行匹配分析         │
│  - 选择得分最高的简历作为推荐简历                                  │
│  - 更新 user_job_matches 记录:                                   │
│    * recommended_resume_id                                      │
│    * resume_match_score                                         │
│    * resume_match_details                                       │
│                                                                  │
│  ⚠️ 注意: 即使简历匹配度较低，也会选择最佳的一份                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ 有推荐简历
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段3: AI深度分析 (异步任务)                                      │
│                                                                  │
│  对所有通过阶段1的匹配 (skill_match_score ≥ 40%):                 │
│  - 提交异步AI分析任务到Celery队列                                 │
│  - 输入:                                                          │
│    * JobAnalysis 完整数据                                        │
│    * 推荐简历的 AnalyzedResume 数据                             │
│    * user_skills 记录 (包含手动添加的技能)                        │
│  - 输出:                                                          │
│    * AI匹配度评分 (可与算法分数对比)                              │
│    * 匹配优势 (strengths)                                        │
│    * 匹配劣势 (weaknesses)                                       │
│    * 简历定制建议 (tailoring_suggestions)                        │
* 求职信撰写策略（coverletter_strategies）(3个角度)
│    * 隐藏匹配点 (hidden_matches)                                 │
│  - 存储到 user_job_matches.ai_analysis (JSON)                   │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  前台展示                                                          │
│  - 显示匹配度百分比 (skill_match_score)                           │
│  - 展示推荐简历                                                    │
│  - 提供AI分析结果 (优势/劣势/定制建议/求职信策略)                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 关键决策点

| 决策点 | 选择 | 理由 |
|--------|------|------|
| **阶段0预筛选** | 岗位名称精确匹配(JSON_CONTAINS) | 减少80%无效计算，性能提升320倍 |
| **岗位标准化** | AI提取标准岗位名称(15-20个预定义) | 控制数据质量，便于精确匹配 |
| **阶段1门槛** | skill_match_score ≥ 40% | 过滤明显不匹配的job，减少无效计算 |
| **阶段2门槛** | 无门槛，选择最佳简历 | 即使匹配度不高，也要给用户提供推荐简历 |
| **AI分析触发** | 所有通过阶段1的匹配 | 为高潜力job提供深度建议 |
| **用户技能来源** | user_skills表(包含手动添加) | 技能可能分散在多份简历中，需要汇总 |
| **简历匹配对象** | 仅正式简历(is_draft=False) | 草稿简历未完成，不适合用于匹配 |

---

## 3. 算法设计

### 3.0 阶段0: 岗位名称预筛选 (性能优化关键)

#### 3.0.1 设计目标

**问题:** 遍历所有用户进行技能匹配计算量巨大
```
1000用户 × 10 jobs = 10,000次技能匹配计算
耗时: ~8分钟
```

**解决方案:** 通过岗位名称快速过滤不相关用户
```
岗位名称预筛选 → 仅保留20%候选用户 → 2,000次技能匹配
耗时: ~1.5分钟 + 10秒(预筛选)
性能提升: 5倍
```

#### 3.0.2 岗位标准化

**Job分析增强 - 标准化岗位名称:**
```python
# JobAnalysis模型新增字段
class JobAnalysis(Base, TimestampMixin):
    # ... 现有字段 ...

    # 标准化岗位名称 (来自预定义列表)
    normalized_job_title: Mapped[Optional[str]] = mapped_column(
        String(150), nullable=True, index=True,
        comment="Standardized job title (e.g., 'Backend Developer')"
    )
```

**Resume分析增强 - 目标岗位列表:**
```python
# AnalyzedResume Schema新增字段
class AnalyzedResume(BaseModel):
    __version__ = "1.1.0"  # 版本升级

    # ... 现有字段 ...

    # 目标岗位类型列表 (3-5个标准岗位名称)
    target_job_titles: list[str] = Field(
        default_factory=list,
        description="List of suitable job titles (e.g., ['Backend Developer', 'Full Stack Developer'])",
        min_items=1,
        max_items=5
    )
```


#### 3.0.3 AI Prompt增强

**Job分析Prompt - 标准化岗位名称:**
```
# 岗位名称标准化

将原始job标题标准化为**标准岗位类型**。

**处理规则:**
1. 去除资历前缀 (Senior, Junior, Lead等)
2. 去除技术栈描述 (Python, React等)
3. 去除工作模式 (Remote, Hybrid等)
4. 匹配到最接近的标准岗位类型

**示例:**
Input: "Senior Backend Engineer (Python/FastAPI) - Remote"
Output: "Backend Developer"
```

#### 3.0.4 数据库查询实现

**MySQL方案:**
```python
async def find_candidate_users_by_title(
    db: AsyncSession,
    job_standard_title: str
) -> List[int]:
    """
    通过岗位名称快速筛选候选用户

    使用JSON_CONTAINS进行精确匹配
    """

    stmt = text("""
        SELECT DISTINCT r.user_id
        FROM resumes r
        WHERE r.is_draft = FALSE
          AND r.analysis_result IS NOT NULL
          AND JSON_CONTAINS(
              r.analysis_result->'$.target_job_titles',
              :job_title
          )
    """)

    result = await db.execute(
        stmt,
        {"job_title": f'"{job_standard_title}"'}  # JSON格式
    )

    user_ids = [row[0] for row in result.fetchall()]

    return user_ids


# 使用示例
job_title = "Backend Developer"
candidate_users = await find_candidate_users_by_title(db, job_title)

# 返回: [1001, 1002, 1003, ...]
# 仅返回简历中target_job_titles包含"Backend Developer"的用户
```

**PostgreSQL方案:**
```sql
SELECT DISTINCT r.user_id
FROM resumes r
WHERE r.is_draft = FALSE
  AND r.analysis_result IS NOT NULL
  AND r.analysis_result->'target_job_titles' ? 'Backend Developer';
```

#### 3.0.5 性能对比

**优化前 (遍历所有用户):**
```
场景: 1000用户 × 10 jobs

计算次数: 10,000次技能匹配
耗时: ~8分钟
```

**优化后 (岗位名称预筛选):**
```
场景: 1000用户 × 10 jobs

阶段0 (预筛选): 10次数据库查询 × 150ms = 1.5秒
  → 筛选出200个候选用户 (20%)

阶段1 (技能匹配): 200用户 × 10 jobs = 2,000次
  → 耗时: ~1.5分钟

总耗时: 1.5秒 + 1.5分钟 ≈ 1.5分钟
性能提升: 5倍+ 🚀
```

#### 3.0.6 匹配示例

**Job分析结果:**
```json
{
  "normalized_job_title": "Backend Developer",
  "required_skills": ["Python", "FastAPI", "PostgreSQL"],
  ...
}
```

**用户简历分析结果:**
```json
{
  "candidate_name": "John Doe",
  "current_title": "Senior Full Stack Developer",
  "target_job_titles": [
    "Full Stack Developer",
    "Backend Developer",
    "Software Engineer"
  ],
  ...
}
```

**匹配逻辑:**
```python
# Job: "Backend Developer"
# User简历: ["Full Stack Developer", "Backend Developer", "Software Engineer"]

# JSON_CONTAINS 查询
# "Backend Developer" IN ["Full Stack Developer", "Backend Developer", "Software Engineer"]
# → 匹配 ✅

# 该用户进入候选名单，执行后续技能匹配
```

---

### 3.1 阶段1: 用户技能库匹配

#### 3.1.1 匹配公式

```
总分 = 必备技能得分(70%) + 可选技能得分(20%) + 软技能得分(10%)
```

#### 3.1.2 详细计算规则

**1. 必备技能得分 (70分)**

```python
必备技能得分 = (Σ 匹配技能的熟练度权重) / (必备技能总数) × 70

熟练度权重映射:
- Expert      → 1.0
- Advanced    → 0.9
- Intermediate → 0.7
- Beginner    → 0.4
```

**示例:**
```
Job需求必备技能: [Python, React, PostgreSQL] (共3个)
用户技能:
  - Python (Expert) → 权重1.0
  - React (Advanced) → 权重0.9
  - Docker (Intermediate) → 不在必备技能中

计算:
(1.0 + 0.9 + 0) / 3 × 70 = 44.3分
```

**2. 可选技能得分 (20分)**

```python
可选技能得分 = (Σ 匹配技能的熟练度权重) / (可选技能总数) × 20

# 使用相同的熟练度权重
# 不匹配可选技能不扣分，匹配则加分
```

**示例:**
```
Job需求可选技能: [Docker, AWS] (共2个)
用户技能:
  - Docker (Intermediate) → 权重0.7
  - AWS (无) → 权重0

计算:
(0.7 + 0) / 2 × 20 = 7分
```

**3. 软技能得分 (10分)**

```python
软技能得分 = (匹配的软技能数量) / (job要求的软技能总数) × 10

# 软技能不考虑熟练度，仅统计匹配数量
```

**示例:**
```
Job需求软技能: [Communication, Teamwork] (共2个)
用户软技能 (skill_type='soft'): [Communication]

计算:
1 / 2 × 10 = 5分
```

#### 3.1.3 完整示例

```
Job需求:
- 必备技能: Python, React, PostgreSQL (3个)
- 可选技能: Docker, AWS (2个)
- 软技能: Communication, Teamwork (2个)

用户技能库 (user_skills):
- Python (Expert, technical)
- React (Advanced, technical)
- Docker (Intermediate, technical)
- Communication (soft)

匹配计算:
1. 必备技能: (1.0 + 0.9 + 0) / 3 × 70 = 44.3分
2. 可选技能: (0.7 + 0) / 2 × 20 = 7.0分
3. 软技能: 1 / 2 × 10 = 5.0分

总分 = 44.3 + 7.0 + 5.0 = 56.3% ✅ 通过阈值(≥40%)
```


#### 3.2.4 选择最佳简历

```python
def find_best_matching_resume(user_id: int, job_analysis: JobAnalysis) -> tuple:
    """
    从用户的所有正式简历中选择最佳匹配

    Returns:
        (resume_id, match_score, match_details)
    """

    # 获取所有正式简历
    resumes = get_formal_resumes(user_id)  # is_draft=False

    if not resumes:
        return None, 0, {}

    best_resume_id = None
    best_score = 0
    best_details = {}

    for resume in resumes:
        analysis = resume.analysis_result  # AnalyzedResume JSON

        if not analysis:
            continue

        # 计算匹配度
        score = calculate_resume_job_match(
            resume_analysis=analysis,
            job_analysis=job_analysis
        )

        if score > best_score:
            best_score = score
            best_resume_id = resume.id
            best_details = {
                "resume_id": resume.id,
                "resume_title": resume.title,
                "skill_score": calculate_skill_score(analysis, job_analysis),
                "experience_score": calculate_experience_score(analysis, job_analysis),
                "relevance_score": calculate_relevance_score(analysis, job_analysis),
                "matched_skills": extract_matched_skills(analysis, job_analysis),
                "experience_years": analysis.get("total_experience_years"),
            }

    return best_resume_id, best_score, best_details
```

---

### 3.3 阶段3: AI深度分析

#### 3.3.1 AI Prompt设计

```python
AI_MATCHING_PROMPT = """
你是一位资深招聘顾问和职业规划师。请基于以下信息进行深度匹配分析。

# 职位信息
## 基本信息
- 职位标题: {job.title}
- 公司名称: {job.advertiser_name}
- 工作地点: {job.location_label}

## 职位要求 (来自AI分析)
- **必备技能**: {job_analysis.required_skills}
- **可选技能**: {job_analysis.preferred_skills}
- **软技能**: {job_analysis.soft_skills}
- **技术栈**: {job_analysis.tech_stack}
- **经验要求**: {job_analysis.experience_years}
- **资质级别**: {job_analysis.seniority}
- **教育要求**: {job_analysis.education_requirement}

## 核心职责
{job_analysis.key_responsibilities}

## 公司文化与招聘优先级
- **文化关键词**: {job_analysis.company_culture_keywords}
- **招聘优先级**: {job_analysis.hiring_priorities}

---

# 候选人信息

## 推荐简历 (算法选择的最佳匹配简历)
```json
{resume_analysis_json}
```

## 完整技能库 (包含其他简历和手动添加的技能)
```json
{user_skills_json}
```

---

# 任务

请综合评估候选人与该职位的匹配度，并提供以下分析:

## 1. AI匹配度评分 (0-100分)
基于以下维度综合评估:
- **技能覆盖度** (40%): 必备技能覆盖率 + 技能熟练度
- **经验匹配度** (30%): 工作年限 + 项目经验相关性 + 资质级别
- **文化契合度** (20%): 软技能 + 公司文化关键词匹配
- **其他因素** (10%): 教育背景 + 认证 + 地点匹配

⚠️ **评分要求**:
- 客观评估，不要过度乐观
- 如果必备技能缺失超过50%，总分不应超过60分
- 如果经验年限明显不足，需要适当扣分

## 2. 核心优势 (3-5条)
候选人在哪些方面**特别符合**该职位要求:
- 优先突出与 `hiring_priorities` 对齐的优势
- 使用具体数据支撑 (如"5年Python经验"而非"有Python经验")
- 关注候选人的量化成就

## 3. 潜在不足 (2-3条)
候选人在哪些方面可能**存在挑战**:
- 重点指出缺失的必备技能
- 提示可能面临的学习曲线
- 诚实评估短板，但避免过于悲观

## 4. 简历定制建议 (3-5条)
为了更好地匹配该职位，简历应如何调整:
- **具体可执行**: 不要泛泛而谈，给出明确的修改建议
- **策略性突出**: 建议重点突出哪些项目经历、技能或成就
- **关键词优化**: 建议补充哪些关键词或描述以通过ATS筛选
- **优先级对齐**: 确保建议与公司的 `hiring_priorities` 一致

示例:
- "在个人简介的第一句明确提及'5年微服务架构经验'，对齐job的核心优先级"
- "将XX项目(使用Python+FastAPI)的描述移至工作经历首位，突出技术栈匹配"
- "在技能清单中添加'敏捷开发'、'跨团队协作'等软技能关键词"

## 5. 隐藏匹配点 (0-3条，可选)
从**完整技能库**中发现的、**简历中未充分体现**但与job相关的技能:
- 识别候选人拥有但未在推荐简历中突出的技能
- 建议如何在简历中补充这些技能的项目经历
- 如果没有发现隐藏匹配点，返回空数组

示例:
- "技能库显示候选人掌握Redis缓存(Intermediate)，而job描述提到高并发系统，建议在简历中补充使用Redis优化性能的项目经历"

---

# 输出格式

**严格按照以下JSON格式输出，不要添加任何额外的文本或markdown标记:**

```json
{
  "ai_match_score": 75,
  "strengths": [
    "5年Python后端开发经验，完全满足job要求的3-5年经验",
    "深度掌握微服务架构，与公司的技术栈(FastAPI+Docker)高度契合",
    "有明确的量化成就('提升系统性能40%')，符合公司对结果导向的文化"
  ],
  "weaknesses": [
    "PostgreSQL经验有限(仅Intermediate)，而job要求为核心必备技能",
    "缺少AWS生产环境经验，可能需要2-3个月的学习曲线"
  ],
  "tailoring_suggestions": [
    "在个人简介的第一句明确提及'5年微服务架构经验，精通Python+FastAPI技术栈'",
    "将Tech Corp的XX项目(使用FastAPI构建RESTful API)移至工作经历首位",
    "补充在YY项目中使用Docker容器化部署的经验，对齐job的DevOps需求",
    "在技能清单中添加'敏捷开发'、'跨团队协作'等软技能关键词"
  ],
  "hidden_matches": [
    "技能库显示候选人掌握Redis缓存(Intermediate)，而job描述提到需要优化高并发系统，建议在简历中补充使用Redis提升系统性能的项目经历"
  ]
}
```

**重要规则**:
1. 所有数组字段必须返回，如果没有内容则返回空数组 `[]`
2. 评分必须是0-100之间的整数
3. 每条建议都要具体、可执行，避免空洞的表述
4. 优先考虑 `hiring_priorities` 中提到的关键点
5. 输出必须是合法的JSON格式，不要包含注释
"""
```

#### 3.3.2 AI分析输出示例

```json
{
  "ai_match_score": 78,
  "strengths": [
    "5年Python后端开发经验，完全满足job要求的3-5年经验要求",
    "深度掌握微服务架构(FastAPI+Docker)，与公司技术栈高度契合",
    "有明确的量化成就('将API响应时间从200ms降至50ms')，符合公司对结果导向的文化",
    "具备数据库优化经验，与job核心职责'database optimization'对齐"
  ],
  "weaknesses": [
    "PostgreSQL经验有限(仅Intermediate级别)，而job要求为核心必备技能，可能需要1-2个月深入学习",
    "缺少AWS云平台生产环境经验，而job可选技能中提到AWS"
  ],
  "tailoring_suggestions": [
    "在个人简介的第一句明确提及'5年微服务架构经验，精通Python+FastAPI+Docker技术栈'，对齐job的hiring priority",
    "将Tech Corp的电商平台项目(使用FastAPI构建RESTful API)移至工作经历首位，突出技术栈匹配",
    "补充在数据库优化方面的具体成就，如'通过索引优化将查询速度提升3倍'，呼应job的核心职责",
    "在技能清单中添加'敏捷开发(Agile)'、'跨团队协作'等软技能关键词，匹配公司文化",
    "在简历末尾添加'持续学习PostgreSQL高级特性'的声明，表明对核心技能的重视"
  ],
  "hidden_matches": [
    "技能库显示候选人掌握Redis缓存(Intermediate)，而job描述提到需要优化高并发系统，建议在简历中补充'使用Redis缓存将系统吞吐量提升50%'的项目经历"
  ]
}
```

---

## 4. 数据库设计

### 4.1 user_job_matches 表

```sql
CREATE TABLE user_job_matches (
    -- ========================================
    -- 主键与外键
    -- ========================================
    id VARCHAR(255) PRIMARY KEY COMMENT 'Primary key (ujm_ prefix)',
    user_id INT NOT NULL COMMENT 'Reference to users.id',
    job_id INT NOT NULL COMMENT 'Reference to seek_jobs.id',

    -- ========================================
    -- 阶段1: 技能库匹配结果
    -- ========================================
    skill_match_score DECIMAL(5,2) NOT NULL COMMENT 'Skill-based match score (0-100)',
    skill_match_details JSON NOT NULL COMMENT 'Detailed skill matching breakdown',

    -- ========================================
    -- 阶段2: 简历匹配结果
    -- ========================================
    recommended_resume_id VARCHAR(255) NULL COMMENT 'Best matching resume ID',
    resume_match_score DECIMAL(5,2) NULL COMMENT 'Resume match score (0-100)',
    resume_match_details JSON NULL COMMENT 'Resume matching breakdown',

    -- ========================================
    -- 阶段3: AI分析结果
    -- ========================================
    ai_match_score DECIMAL(5,2) NULL COMMENT 'AI-evaluated match score (0-100)',
    ai_analysis JSON NULL COMMENT 'AI analysis result (strengths, weaknesses, suggestions)',

    -- ========================================
    -- 元数据
    -- ========================================
    matching_algorithm_version VARCHAR(20) NOT NULL COMMENT 'Algorithm version (e.g., v1.0.0)',
    calculated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When matching was calculated',
    ai_analyzed_at TIMESTAMP NULL COMMENT 'When AI analysis was completed',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- ========================================
    -- 索引与约束
    -- ========================================
    UNIQUE KEY uk_user_job (user_id, job_id),
    INDEX idx_user_skill_score (user_id, skill_match_score DESC),
    INDEX idx_job_skill_score (job_id, skill_match_score DESC),
    INDEX idx_user_resume_score (user_id, resume_match_score DESC),
    INDEX idx_calculated_at (calculated_at),

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES seek_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (recommended_resume_id) REFERENCES resumes(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Job-User matching results with AI analysis';
```

### 4.2 skill_match_details JSON结构

```json
{
  "matched_required_skills": [
    {
      "skill": "Python",
      "user_proficiency": "Expert",
      "weight": 1.0
    },
    {
      "skill": "React",
      "user_proficiency": "Advanced",
      "weight": 0.9
    }
  ],
  "missing_required_skills": ["PostgreSQL", "Docker"],
  "matched_preferred_skills": [
    {
      "skill": "AWS",
      "user_proficiency": "Intermediate",
      "weight": 0.7
    }
  ],
  "missing_preferred_skills": ["Kubernetes"],
  "matched_soft_skills": ["Communication", "Problem-solving"],
  "missing_soft_skills": ["Leadership"],
  "score_breakdown": {
    "required_score": 44.3,
    "preferred_score": 7.0,
    "soft_score": 5.0
  }
}
```

### 4.3 resume_match_details JSON结构

```json
{
  "resume_id": "res_xxx123",
  "resume_title": "Full Stack Developer Resume",
  "skill_score": 27.3,
  "experience_score": 25.0,
  "relevance_score": 17.9,
  "experience_years": 5,
  "experience_match": "满足要求(3-5年)",
  "matched_skills": [
    {"skill": "Python", "proficiency": "Expert"},
    {"skill": "React", "proficiency": "Advanced"},
    {"skill": "Docker", "proficiency": "Intermediate"}
  ],
  "work_relevance": {
    "overall_score": 0.85,
    "relevant_experiences": [
      {
        "company": "Tech Corp",
        "role": "Senior Backend Developer",
        "tech_overlap": ["Python", "FastAPI", "PostgreSQL"],
        "tech_overlap_score": 0.75,
        "keyword_match_score": 0.67,
        "relevance_score": 0.72
      }
    ]
  }
}
```

### 4.4 ai_analysis JSON结构

```json
{
  "ai_match_score": 78,
  "strengths": [
    "5年Python后端开发经验，完全满足job要求",
    "深度掌握微服务架构，与公司技术栈高度契合",
    "有明确的量化成就，符合公司对结果导向的文化"
  ],
  "weaknesses": [
    "PostgreSQL经验有限，可能需要学习曲线",
    "缺少AWS生产环境经验"
  ],
  "tailoring_suggestions": [
    "在个人简介中明确提及'5年微服务架构经验'",
    "将使用Python+FastAPI的项目放在首位",
    "补充Docker容器化经验"
  ],
  "coverletter_strategies": [],
  "hidden_matches": [
    "技能库显示掌握Redis缓存，建议在简历中补充相关项目"
  ]
}
```

---

## 5. 任务实现设计

### 5.1 Celery任务定义 (优化版)

```python
# app/modules/matching/tasks.py

from celery import Task
from app.core.celery_app import celery_app
from app.core.database import get_db
from datetime import datetime, timezone, timedelta

@celery_app.task(
    name="matching.calculate_job_user_matches",
    bind=True,
    max_retries=3
)
def calculate_job_user_matches_task(self: Task):
    """
    定时任务: 计算新job与用户的匹配度 (优化版)

    执行频率: 每小时
    触发条件: job_analyses 表中有新分析完成的job (最近1小时)

    流程:
    0. 获取最近1小时内新分析的job
    1. 【优化】阶段0: 岗位名称预筛选 (数据库查询)
    2. 阶段1: 技能库匹配 (仅对候选用户)
    3. 阶段2: 简历匹配
    4. 阶段3: 提交AI分析任务 (异步)
    """

    async def _run():
        async for db in get_db():
            try:
                # 0. 获取最近1小时内分析的job
                one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
                recent_jobs = await JobAnalysisRepository.get_recent_analyses(
                    db=db,
                    since=one_hour_ago
                )

                logger.info(f"Found {len(recent_jobs)} recently analyzed jobs")

                total_potential_matches = 0
                total_after_title_filter = 0
                total_after_skill_filter = 0
                ai_analysis_submitted = 0

                for job_analysis in recent_jobs:
                    # ========================================
                    # 【新增】阶段0: 岗位名称预筛选
                    # ========================================
                    candidate_user_ids = await find_candidate_users_by_title(
                        db=db,
                        job_standard_title=job_analysis.normalized_job_title
                    )

                    all_users_count = await UserRepository.count_active_users(db)
                    total_potential_matches += all_users_count
                    total_after_title_filter += len(candidate_user_ids)

                    logger.info(
                        f"Job '{job_analysis.normalized_job_title}': "
                        f"Title filter reduced candidates from {all_users_count} "
                        f"to {len(candidate_user_ids)} "
                        f"({len(candidate_user_ids)/max(all_users_count,1)*100:.1f}%)"
                    )

                    # ========================================
                    # 阶段1: 技能库匹配 (仅对候选用户)
                    # ========================================
                    for user_id in candidate_user_ids:
                        user_skills = await UserSkillRepository.get_by_user_id(
                            db=db,
                            user_id=user_id
                        )

                        skill_score, skill_details = calculate_user_skill_match(
                            user_skills=user_skills,
                            job_analysis=job_analysis
                        )

                        # 如果不通过技能匹配阈值，跳过
                        if skill_score < 40:
                            continue

                        total_after_skill_filter += 1

                        # ========================================
                        # 阶段2: 简历匹配
                        # ========================================
                        resume_id, resume_score, resume_details = await find_best_matching_resume(
                            db=db,
                            user_id=user_id,
                            job_analysis=job_analysis
                        )

                        # 创建或更新匹配记录
                        match = await UserJobMatchRepository.upsert(
                            db=db,
                            user_id=user_id,
                            job_id=job_analysis.job_id,
                            skill_match_score=skill_score,
                            skill_match_details=skill_details,
                            recommended_resume_id=resume_id,
                            resume_match_score=resume_score,
                            resume_match_details=resume_details,
                            matching_algorithm_version="v1.1.0"  # 版本升级
                        )

                        await db.commit()

                        # ========================================
                        # 阶段3: 提交AI分析任务 (异步)
                        # ========================================
                        if resume_id:  # 有推荐简历才进行AI分析
                            analyze_match_with_ai_task.delay(
                                match_id=match.id,
                                user_id=user_id,
                                job_id=job_analysis.job_id,
                                resume_id=resume_id
                            )
                            ai_analysis_submitted += 1

                # 统计日志
                logger.info(
                    f"Matching completed:\n"
                    f"  - Potential matches: {total_potential_matches}\n"
                    f"  - After title filter: {total_after_title_filter} "
                    f"({total_after_title_filter/max(total_potential_matches,1)*100:.1f}%)\n"
                    f"  - After skill filter: {total_after_skill_filter} "
                    f"({total_after_skill_filter/max(total_potential_matches,1)*100:.1f}%)\n"
                    f"  - AI analysis submitted: {ai_analysis_submitted}\n"
                    f"  - Filter efficiency: "
                    f"{(1 - total_after_title_filter/max(total_potential_matches,1))*100:.1f}% reduction"
                )

            except Exception as e:
                logger.error(f"Error in calculate_job_user_matches_task: {e}")
                raise

    return asyncio.run(_run())


@celery_app.task(
    name="matching.analyze_match_with_ai",
    bind=True,
    max_retries=2,
    retry_backoff=True
)
def analyze_match_with_ai_task(
    self: Task,
    match_id: str,
    user_id: int,
    job_id: int,
    resume_id: str
):
    """
    AI深度分析任务 (异步执行)

    流程:
    1. 加载 job_analysis, resume_analysis, user_skills
    2. 构造prompt并调用LLM
    3. 解析结果并更新 user_job_matches 记录
    """

    async def _run():
        async for db in get_db():
            try:
                # 1. 加载数据
                job_analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)
                job = await JobRepository.get_by_id(db, job_id)
                resume = await ResumeRepository.get_by_id(db, resume_id)
                user_skills = await UserSkillRepository.get_by_user_id(db, user_id)

                if not all([job_analysis, job, resume, resume.analysis_result, user_skills]):
                    raise ValueError("Missing required data for AI analysis")

                # 2. 调用LLM
                ai_result = await call_llm_for_matching(
                    job=job,
                    job_analysis=job_analysis,
                    resume_analysis=resume.analysis_result,
                    user_skills=user_skills
                )

                # 3. 更新匹配记录
                await UserJobMatchRepository.update_ai_analysis(
                    db=db,
                    match_id=match_id,
                    ai_match_score=ai_result["ai_match_score"],
                    ai_analysis=ai_result,
                    ai_analyzed_at=datetime.now(timezone.utc)
                )

                await db.commit()

                logger.info(f"AI analysis completed for match {match_id}")

            except Exception as e:
                logger.error(f"Error in analyze_match_with_ai_task: {e}")
                # 重试逻辑
                if self.request.retries < self.max_retries:
                    raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
                else:
                    # 达到最大重试次数，记录失败但不阻塞
                    logger.error(f"AI analysis failed permanently for match {match_id}")

    return asyncio.run(_run())
```

### 5.2 定时任务调度配置

```python
# app/core/celery_app.py

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # 每小时执行一次job匹配计算
    "calculate-job-matches-hourly": {
        "task": "matching.calculate_job_user_matches",
        "schedule": crontab(minute=0),  # 每小时的第0分钟执行
        "options": {
            "queue": "matching",
            "expires": 3000,  # 50分钟后过期，避免重叠执行
        }
    },
}

# 队列配置
celery_app.conf.task_routes = {
    "matching.calculate_job_user_matches": {"queue": "matching"},
    "matching.analyze_match_with_ai": {"queue": "ai_analysis"},
}
```

---

## 6. API设计

### 6.1 获取用户的匹配job列表

```python
# app/modules/matching/router.py

@router.get("/my-matches", response_model=list[schemas.UserJobMatchResponse])
async def get_my_job_matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    min_score: float = Query(40, ge=0, le=100, description="Minimum match score"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    获取当前用户的匹配job列表

    Query参数:
    - min_score: 最低匹配度 (默认40%)
    - limit: 每页数量
    - offset: 偏移量

    返回:
    - 按 skill_match_score 降序排列
    - 包含job基本信息、匹配度、推荐简历、AI分析
    """

    matches = await UserJobMatchRepository.get_user_matches(
        db=db,
        user_id=current_user.id,
        min_score=min_score,
        limit=limit,
        offset=offset
    )

    # 加载关联的job和resume数据
    results = []
    for match in matches:
        job = await JobRepository.get_by_id(db, match.job_id)
        resume = None
        if match.recommended_resume_id:
            resume = await ResumeRepository.get_by_id(db, match.recommended_resume_id)

        results.append(
            schemas.UserJobMatchResponse(
                id=match.id,
                job=schemas.JobBriefInfo.from_orm(job),
                skill_match_score=match.skill_match_score,
                resume_match_score=match.resume_match_score,
                ai_match_score=match.ai_match_score,
                recommended_resume=schemas.ResumeBriefInfo.from_orm(resume) if resume else None,
                skill_match_details=match.skill_match_details,
                ai_analysis=match.ai_analysis,
                calculated_at=match.calculated_at,
                ai_analyzed_at=match.ai_analyzed_at,
            )
        )

    return results


@router.get("/matches/{job_id}", response_model=schemas.UserJobMatchDetailResponse)
async def get_job_match_detail(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定job的匹配详情

    返回:
    - 完整的匹配分析结果
    - AI分析的详细建议
    - 推荐简历信息
    """

    match = await UserJobMatchRepository.get_by_user_and_job(
        db=db,
        user_id=current_user.id,
        job_id=job_id
    )

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # 加载完整的job和resume信息
    job = await JobRepository.get_by_id(db, job_id)
    job_analysis = await JobAnalysisRepository.get_by_job_id(db, job_id)

    resume = None
    if match.recommended_resume_id:
        resume = await ResumeRepository.get_by_id(db, match.recommended_resume_id)

    return schemas.UserJobMatchDetailResponse(
        id=match.id,
        job=schemas.JobDetailInfo.from_orm(job),
        job_analysis=schemas.JobAnalysisInfo.from_orm(job_analysis),
        skill_match_score=match.skill_match_score,
        skill_match_details=match.skill_match_details,
        resume_match_score=match.resume_match_score,
        resume_match_details=match.resume_match_details,
        recommended_resume=schemas.ResumeDetailInfo.from_orm(resume) if resume else None,
        ai_match_score=match.ai_match_score,
        ai_analysis=match.ai_analysis,
        calculated_at=match.calculated_at,
        ai_analyzed_at=match.ai_analyzed_at,
    )
```

### 6.2 响应Schema定义

```python
# app/modules/matching/schemas.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class JobBriefInfo(BaseModel):
    """Job简要信息"""
    id: int
    title: str
    advertiser_name: Optional[str]
    location_label: Optional[str]
    work_types_label: Optional[str]
    salary_label: Optional[str]
    listed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ResumeBriefInfo(BaseModel):
    """简历简要信息"""
    id: str
    title: str

    class Config:
        from_attributes = True


class UserJobMatchResponse(BaseModel):
    """匹配结果响应 (列表)"""
    id: str
    job: JobBriefInfo
    skill_match_score: float = Field(..., description="Skill match score (0-100)")
    resume_match_score: Optional[float] = Field(None, description="Resume match score (0-100)")
    ai_match_score: Optional[float] = Field(None, description="AI match score (0-100)")
    recommended_resume: Optional[ResumeBriefInfo]

    # 仅包含简要的匹配详情 (供列表展示)
    skill_match_details: dict
    ai_analysis: Optional[dict] = None

    calculated_at: datetime
    ai_analyzed_at: Optional[datetime]


class UserJobMatchDetailResponse(BaseModel):
    """匹配结果详情响应"""
    id: str
    job: JobDetailInfo  # 完整job信息
    job_analysis: JobAnalysisInfo  # job分析结果

    # 阶段1: 技能匹配
    skill_match_score: float
    skill_match_details: dict

    # 阶段2: 简历匹配
    resume_match_score: Optional[float]
    resume_match_details: Optional[dict]
    recommended_resume: Optional[ResumeDetailInfo]

    # 阶段3: AI分析
    ai_match_score: Optional[float]
    ai_analysis: Optional[dict]

    calculated_at: datetime
    ai_analyzed_at: Optional[datetime]
```

---

## 7. Repository实现

### 7.1 UserJobMatchRepository

```python
# app/modules/matching/repository.py

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.matching.models import UserJobMatch
from app.shared.id_generator import generate_id
from datetime import datetime, timezone
from typing import Optional

class UserJobMatchRepository:

    @staticmethod
    async def upsert(
        db: AsyncSession,
        user_id: int,
        job_id: int,
        skill_match_score: float,
        skill_match_details: dict,
        recommended_resume_id: Optional[str] = None,
        resume_match_score: Optional[float] = None,
        resume_match_details: Optional[dict] = None,
        matching_algorithm_version: str = "v1.0.0"
    ) -> UserJobMatch:
        """
        创建或更新匹配记录

        如果记录已存在，更新所有字段
        """

        # 查询是否存在
        stmt = select(UserJobMatch).where(
            and_(
                UserJobMatch.user_id == user_id,
                UserJobMatch.job_id == job_id
            )
        )
        result = await db.execute(stmt)
        match = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if match:
            # 更新现有记录
            match.skill_match_score = skill_match_score
            match.skill_match_details = skill_match_details
            match.recommended_resume_id = recommended_resume_id
            match.resume_match_score = resume_match_score
            match.resume_match_details = resume_match_details
            match.matching_algorithm_version = matching_algorithm_version
            match.calculated_at = now
            match.updated_at = now

            # 重新计算时清空旧的AI分析
            match.ai_match_score = None
            match.ai_analysis = None
            match.ai_analyzed_at = None
        else:
            # 创建新记录
            match = UserJobMatch(
                id=generate_id("ujm"),
                user_id=user_id,
                job_id=job_id,
                skill_match_score=skill_match_score,
                skill_match_details=skill_match_details,
                recommended_resume_id=recommended_resume_id,
                resume_match_score=resume_match_score,
                resume_match_details=resume_match_details,
                matching_algorithm_version=matching_algorithm_version,
                calculated_at=now,
            )
            db.add(match)

        return match

    @staticmethod
    async def update_ai_analysis(
        db: AsyncSession,
        match_id: str,
        ai_match_score: float,
        ai_analysis: dict,
        ai_analyzed_at: datetime
    ) -> UserJobMatch:
        """
        更新AI分析结果
        """

        stmt = select(UserJobMatch).where(UserJobMatch.id == match_id)
        result = await db.execute(stmt)
        match = result.scalar_one_or_none()

        if not match:
            raise ValueError(f"UserJobMatch {match_id} not found")

        match.ai_match_score = ai_match_score
        match.ai_analysis = ai_analysis
        match.ai_analyzed_at = ai_analyzed_at
        match.updated_at = datetime.now(timezone.utc)

        return match

    @staticmethod
    async def get_user_matches(
        db: AsyncSession,
        user_id: int,
        min_score: float = 40,
        limit: int = 20,
        offset: int = 0
    ) -> list[UserJobMatch]:
        """
        获取用户的匹配列表

        按 skill_match_score 降序排列
        """

        stmt = (
            select(UserJobMatch)
            .where(
                and_(
                    UserJobMatch.user_id == user_id,
                    UserJobMatch.skill_match_score >= min_score
                )
            )
            .order_by(desc(UserJobMatch.skill_match_score))
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_user_and_job(
        db: AsyncSession,
        user_id: int,
        job_id: int
    ) -> Optional[UserJobMatch]:
        """
        获取指定用户与job的匹配记录
        """

        stmt = select(UserJobMatch).where(
            and_(
                UserJobMatch.user_id == user_id,
                UserJobMatch.job_id == job_id
            )
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()
```


## 10. 实施清单

### 10.1 数据库迁移

```bash
# 创建user_job_matches表
alembic revision --autogenerate -m "Create user_job_matches table"
alembic upgrade head
```

### 10.2 代码文件清单

**新建文件:**
```
backend/app/modules/matching/
├── __init__.py
├── models.py              # UserJobMatch模型
├── schemas.py             # API响应Schema
├── repository.py          # UserJobMatchRepository
├── service.py             # 匹配算法实现
├── router.py              # API路由
└── tasks.py               # Celery任务
```

**修改文件:**
```
backend/app/api/v1/__init__.py         # 注册matching路由
backend/app/core/celery_app.py         # 添加定时任务配置
backend/app/shared/enums.py            # (可选)添加匹配相关枚举
```

### 10.3 实施步骤

**Phase 1: 数据层 (2小时)**
1. ✅ 定义UserJobMatch模型
2. ✅ 创建数据库迁移
3. ✅ 实现UserJobMatchRepository

**Phase 2: 匹配算法 (5小时)**
4. ✅ 实现阶段0: 岗位名称预筛选 (数据库查询)
5. ✅ 实现阶段1: 技能库匹配算法
6. ✅ 实现阶段2: 简历匹配算法
7. ✅ 实现技能名称标准化
8. ✅ 单元测试算法逻辑

**Phase 3: AI分析 (3小时)**
8. ✅ 设计AI Prompt
9. ✅ 实现LLM调用逻辑
10. ✅ 解析AI返回结果
11. ✅ 测试AI分析准确性

**Phase 4: Celery任务 (3小时)**
12. ✅ 实现主任务: calculate_job_user_matches_task
13. ✅ 实现AI任务: analyze_match_with_ai_task
14. ✅ 配置定时任务调度
15. ✅ 测试任务执行流程

**Phase 5: API层 (2小时)**
16. ✅ 实现GET /my-matches接口
17. ✅ 实现GET /matches/{job_id}接口
18. ✅ 定义响应Schema
19. ✅ 测试API端点

**Phase 6: 集成测试 (2小时)**
20. ✅ 端到端测试完整流程
21. ✅ 验证匹配准确性
22. ✅ 性能测试与优化

**总计: ~17小时**

---

## 11. 测试场景

### 11.1 功能测试

**场景1: 新job触发匹配计算**
```
1. 创建新job并完成job_analysis
2. 等待定时任务执行
3. 验证:
   - user_job_matches表中创建了记录
   - skill_match_score正确计算
   - 推荐了最佳匹配简历
   - AI分析任务已提交
```

**场景2: 用户技能更新触发重新计算**
```
1. 用户添加新技能到user_skills
2. 触发重新计算 (手动或下次定时任务)
3. 验证:
   - 匹配度更新
   - 推荐简历可能变化
```

**场景3: 高匹配度job展示**
```
1. 用户访问匹配job列表
2. 验证:
   - 按匹配度降序排列
   - 显示推荐简历
   - AI分析结果正确展示
```

### 11.2 边界测试

**测试用例:**
- 用户无技能 → skill_match_score = 0
- 用户无正式简历 → recommended_resume_id = NULL
- Job无技能要求 → 如何处理?
- AI调用失败 → 重试机制
- 技能名称大小写不一致 → 标准化处理

### 11.3 性能测试

**测试场景:**
- 1000用户 × 10 jobs = 10,000次匹配计算
- 验证任务执行时间 < 30分钟
- 验证数据库查询性能
- 验证AI调用并发处理

---

## 12. 监控与告警

### 12.1 关键指标

```python
# 定时任务执行监控
- 执行时长
- 成功率
- 匹配记录创建数量
- AI分析任务提交数量

# AI分析监控
- AI调用成功率
- AI调用耗时
- AI成本统计
- 异常prompt识别

# 业务指标
- 平均匹配度分布
- 高匹配job比例 (≥80%)
- 用户申请转化率
```

### 12.2 告警规则

```python
# 定时任务失败告警
if task_failed:
    alert("Job matching task failed")

# AI成本超预算告警
if daily_ai_cost > BUDGET_THRESHOLD:
    alert("AI cost exceeded daily budget")

# 匹配质量告警
if avg_match_score < 50:
    alert("Average match score too low, check algorithm")
```

---

## 13. 未来优化方向

### 13.1 算法优化

- [ ] 引入机器学习模型预测匹配度
- [ ] 基于用户申请历史优化权重
- [ ] 考虑job的申请热度和竞争度

### 13.2 性能优化

- [ ] 增量计算: 仅对变化的数据重新计算
- [ ] 缓存策略: Redis缓存高频访问的匹配结果
- [ ] 批量AI分析: 降低API调用成本

### 13.3 功能增强

- [ ] 用户反馈机制: 让用户标记匹配准确性
- [ ] 自定义权重: 允许用户调整技能/经验的权重
- [ ] 匹配解释: 可视化展示匹配度计算过程

---

**文档版本:** 1.1.0
**最后更新:** 2025-12-09
**负责人:** AI Assistant


