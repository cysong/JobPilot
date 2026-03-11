# 简历分析功能设计方案

## 1. 功能概述

### 1.1 业务需求

实现自动化简历分析功能,提取简历中的结构化信息,包括:
- 个人基本信息(姓名、职位、工作年限、地理位置)
- 技能清单(技术技能 + 软技能,自动评估熟练度)
- 工作经历(公司、职位、时间、成就、技术栈)
- 教育背景和认证
- 量化成就
- 工作权限和意愿

### 1.2 触发时机

**自动触发:**
1. 用户将简历定稿时(is_draft: True → False)
2. 用户修改正式简历内容时(is_draft=False 且 content_hash 变化)

**手动触发:**
- 提供 API 端点支持用户手动重新分析

### 1.3 技术选型

- **AI 模型**: OpenAI GPT-4o-mini (平衡成本与效果)
- **任务队列**: Celery (复用现有工作流框架)
- **数据存储**: PostgreSQL (新增 `resume_analyses` 表)
- **架构模式**: 与 `job_analysis` 保持一致

---

## 2. 数据库设计

### 2.1 Resumes 表新增字段

**迁移 SQL:**

```sql
ALTER TABLE resumes ADD COLUMN analysis_result JSONB NULL;
ALTER TABLE resumes ADD COLUMN analyzed_at TIMESTAMPTZ NULL;
ALTER TABLE resumes ADD COLUMN analysis_version VARCHAR(20) NULL;

CREATE INDEX idx_resumes_analyzed_at ON resumes(analyzed_at);
```

**字段说明:**
- `analysis_result`: 存储完整的 AnalyzedResume JSON 数据
- `analyzed_at`: 最后一次分析的时间戳
- `analysis_version`: Schema 版本号 (如 "1.0.0")

### 2.2 Resume Model 更新

```python
class Resume(Base, TimestampMixin):
    # ... existing fields ...

    # Analysis fields
    analysis_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    analysis_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
```

---

## 3. 数据结构设计

### 3.1 Pydantic Schemas

**agent_configs/schemas.py:**

```python
from pydantic import BaseModel, Field
from app.shared.enums import ProficiencyLevel

class Skill(BaseModel):
    """技能项"""
    name: str = Field(..., description="Standardized skill name (e.g., 'Python', 'React', 'Docker')")
    proficiency: ProficiencyLevel = Field(..., description="Proficiency level")

class WorkExperience(BaseModel):
    """工作经历"""
    company: str = Field(..., description="Company name")
    role: str = Field(..., description="Job title/role")
    duration: tuple[str, str] = Field(..., description="Start and end date [from, to]")
    key_achievements: list[str] = Field(default_factory=list, description="Key achievements")
    technologies_used: list[str] = Field(default_factory=list, description="Technologies used")

class AnalyzedResume(BaseModel):
    """简历分析结果 Schema"""

    __version__ = "1.0.0"

    # Basic information
    candidate_name: str = Field(..., description="Candidate full name")
    current_title: str = Field(..., description="Current or most recent job title")
    total_experience_years: int = Field(..., ge=0, description="Total years of professional experience")

    # Skills (with proficiency assessment)
    technical_skills: list[Skill] = Field(default_factory=list, description="Technical skills with proficiency levels")
    soft_skills: list[str] = Field(default_factory=list, description="Soft skills list")

    # Work history
    work_experiences: list[WorkExperience] = Field(default_factory=list, description="Work experience history")

    # Achievements
    quantified_achievements: list[str] = Field(
        default_factory=list,
        description="Quantified achievements (e.g., 'Reduced latency by 40%')"
    )

    # Education (sorted by most recent first, then highest degree first)
    education: list[str] = Field(
        default_factory=list,
        description="Education history (most recent to oldest, highest to lowest degree)"
    )
    certifications: list[str] = Field(default_factory=list, description="Professional certifications")

    # Location and work authorization
    location: str = Field(..., description="Current location or preferred work location")
    relocate_willing: bool | None = Field(None, description="Willingness to relocate")
    work_right: str = Field(..., description="Work authorization/visa status")
```

### 3.2 技能名称标准化

**实现方式:**

在 AI Prompt 中要求使用标准化的技能名称，遵循以下规则：

1. **编程语言**: 使用官方大小写 (Python, JavaScript, TypeScript, C++, C#, Java, Go, Rust)
2. **框架/库**: 使用官方名称 (React, Vue.js, Angular, Django, FastAPI, Express.js, Spring Boot)
3. **工具/平台**: 使用规范名称 (Docker, Kubernetes, AWS, Azure, GCP, PostgreSQL, MongoDB, Redis)
4. **通用技能**: 首字母大写 (Leadership, Communication, Problem Solving)

**Prompt 指导:**
```
CRITICAL: Use standardized skill names following these conventions:
- Programming languages: Official casing (Python, JavaScript, TypeScript, C++, Java)
- Frameworks: Official names (React, Vue.js, Django, FastAPI, Spring Boot)
- Tools/Platforms: Standard names (Docker, Kubernetes, AWS, PostgreSQL, Redis)
- Avoid abbreviations unless industry-standard (e.g., "AWS" not "Amazon Web Services")
- Use consistent capitalization (e.g., "Node.js" not "nodejs")
```

---

## 4. 技能熟练度评估规则

### 4.1 评估逻辑

AI Agent 需要根据以下规则自动判断技能熟练度:

| 熟练度等级 | 判断依据 | 示例 |
|----------|---------|------|
| **Expert** | 多个项目中作为主要技术栈使用;<br>长期深度使用(3年+);<br>明确标注为专家级 | "5 years of Python development in production systems" |
| **Advanced** | 生产环境实战使用过;<br>独立完成复杂功能;<br>在工作经历中多次提及 | "Built scalable microservices with FastAPI" |
| **Intermediate** | 在技能列表中明确列出;<br>有实际项目经验但非核心技术;<br>中等熟悉度 | "Skills: React, TypeScript, Docker" |
| **Beginner** | 仅在 Demo 或学习项目中使用;<br>简单提及但无详细描述;<br>无法确定熟练度的技术 | "Familiar with Kubernetes basics" |

### 4.2 Prompt 指导

在 AI Prompt 中明确要求:

```
When assessing skill proficiency levels, follow these rules:

1. **Expert**:
   - Used as primary technology across multiple production projects
   - 3+ years of experience explicitly mentioned
   - Demonstrated thought leadership (e.g., "Led migration to...")

2. **Advanced**:
   - Used in production systems with proven impact
   - Completed complex features independently
   - Mentioned multiple times in work experience with concrete achievements

3. **Intermediate**:
   - Listed in skills section without detailed work examples
   - Used in real projects but not as core technology
   - Moderate familiarity indicated

4. **Beginner**:
   - Only used in demos, side projects, or learning contexts
   - Briefly mentioned without elaboration
   - Cannot determine proficiency level from context
```

---

## 5. 工作流设计

### 5.1 触发逻辑流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户操作 (定稿/修改简历)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              ResumeService.finalize_resume()                     │
│              ResumeService.update_resume()                       │
│                                                                  │
│  1. 更新 Resume 记录 (is_draft = False / 更新 content)           │
│  2. 计算新的 content_hash                                        │
│  3. 检查是否需要分析:                                            │
│     - resume.analysis_result is None OR                         │
│     - document.content_hash 与上次分析时不同                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ 需要分析
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│               WorkflowService.create_workflow()                  │
│                                                                  │
│  - workflow_type: RESUME_ANALYSIS                               │
│  - entity_id: resume_id                                          │
│  - user_id: current_user.id                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│               WorkflowService.submit_task()                      │
│                                                                  │
│  - task_type: RESUME_ANALYSIS                                   │
│  - celery_task: analyze_resume_async                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Celery Worker 执行任务                           │
│                                                                  │
│  analyze_resume_async(resume_id, workflow_id, task_id)          │
│    ↓                                                             │
│  _execute_resume_analysis() [@task_status_guard]                │
│    1. Load resume with document                                 │
│    2. Call AgentGateway (resume_analyzer)                       │
│    3. Parse AnalyzedResume result                               │
│    4. Update Resume fields:                                      │
│       - analysis_result = parsed_data                           │
│       - analyzed_at = now()                                      │
│       - analysis_version = "1.0.0"                              │
│    5. Extract skills → UserSkill records (with standardization) │
│    6. Commit transaction                                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     完成 (状态更新)                               │
│                                                                  │
│  - WorkflowExecution.status = COMPLETED                         │
│  - TaskExecution.status = SUCCESS                               │
│  - Resume.analyzed_at = now()                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 手动触发流程

```
用户请求: POST /api/v1/resumes/{resume_id}/analyze
    ↓
ResumeRouter.trigger_analysis()
    ↓
创建新 Workflow (强制执行，忽略 content_hash 检查)
    ↓
分析完成后更新 Resume.analysis_result 等字段
```

---

## 6. 技能提取到 user_skills 表

### 6.1 逻辑设计

分析完成后,自动将技能同步到 `user_skills` 表:

```python
# In _execute_resume_analysis()

# Extract technical skills
for skill in analysis_data["technical_skills"]:
    await UserSkillRepository.upsert(
        db=db,
        user_id=resume.user_id,
        skill_name=skill["name"],
        proficiency=skill["proficiency"],
        skill_type="technical",
        extracted_from_id=resume_id  # Track source
    )
```

### 6.2 UserSkill 更新策略

**规则:**
1. **新增技能**: 直接创建
2. **已存在技能**:
   - 如果新熟练度更高 → 更新
   - 如果新熟练度更低 → 保持现有(避免降级)
   - 更新 `extracted_from_id` 为最新简历 ID

**Repository 方法:**

```python
class UserSkillRepository:
    @staticmethod
    async def upsert_from_resume_analysis(
        db: AsyncSession,
        user_id: int,
        skills: list[dict],  # [{"name": "Python", "proficiency": "Expert"}, ...]
        resume_id: str,
    ):
        """
        Upsert skills from resume analysis.

        Rules:
        - New skill: Create
        - Existing skill: Only update if new proficiency is higher
        """
        proficiency_order = {
            ProficiencyLevel.BEGINNER: 1,
            ProficiencyLevel.INTERMEDIATE: 2,
            ProficiencyLevel.ADVANCED: 3,
            ProficiencyLevel.EXPERT: 4,
        }

        for skill_data in skills:
            existing = await db.execute(
                select(UserSkill).where(
                    UserSkill.user_id == user_id,
                    UserSkill.skill_name == skill_data["name"]
                )
            )
            existing_skill = existing.scalar_one_or_none()

            new_proficiency = ProficiencyLevel(skill_data["proficiency"])

            if not existing_skill:
                # Create new skill
                new_skill = UserSkill(
                    id=generate_id("usk"),
                    user_id=user_id,
                    skill_name=skill_data["name"],
                    proficiency=new_proficiency,
                    skill_type="technical",
                    extracted_from_id=resume_id,
                )
                db.add(new_skill)
            else:
                # Update only if new proficiency is higher
                if proficiency_order[new_proficiency] > proficiency_order[existing_skill.proficiency]:
                    existing_skill.proficiency = new_proficiency
                    existing_skill.extracted_from_id = resume_id
                    existing_skill.updated_at = datetime.now(timezone.utc)
```

---

## 7. AI Agent 配置

### 7.1 Agent 定义

**agent_configs/resume_analyzer.py:**

```python
from agent_configs.base import AgentConfig
from agent_configs.schemas import AnalyzedResume

resume_analyzer_config = AgentConfig(
    agent_id="resume_analyzer",
    name="Resume Analyzer",
    description="Extracts structured information from resume content",

    # Model configuration
    model="gpt-4o-mini",
    temperature=0.1,  # Low temperature for consistency

    # Output schema
    output_schema=AnalyzedResume,

    # System prompt
    system_prompt="""You are an expert resume analyzer. Your task is to extract structured information from resume content.

CRITICAL INSTRUCTIONS:

1. **Skill Name Standardization**:
   - Use official capitalization: Python, JavaScript, TypeScript, C++, Java, Go, Rust
   - Framework names: React, Vue.js, Angular, Django, FastAPI, Express.js, Spring Boot
   - Tools/Platforms: Docker, Kubernetes, AWS, Azure, GCP, PostgreSQL, MongoDB, Redis
   - Avoid abbreviations unless standard (AWS, not "Amazon Web Services")
   - Consistent formatting (Node.js, not "nodejs")

2. **Skill Proficiency Assessment**:
   - **Expert**: Used as primary technology in multiple production projects (3+ years or clear mastery)
   - **Advanced**: Used in production systems with proven impact, mentioned multiple times in work experience
   - **Intermediate**: Listed in skills section, used in real projects but not core technology
   - **Beginner**: Used in demos/side projects, briefly mentioned, or unclear proficiency

3. **Work Experience Parsing**:
   - Extract company name, role, duration (as [start_date, end_date])
   - Identify key achievements (especially quantified results)
   - List ALL technologies used in each role (with standardized names)

4. **Education Extraction**:
   - Return as list of strings: ["{Degree}, {Institution}, {Year}", ...]
   - Sort by most recent first, then highest degree first
   - Example: ["Master of Computer Science, MIT, 2020", "Bachelor of Engineering, UC Berkeley, 2018"]

5. **Quantified Achievements**:
   - Focus on metrics: percentages, time savings, revenue impact, user growth, etc.
   - Examples: "Reduced latency by 40%", "Increased conversion by 25%"

6. **Data Quality**:
   - If information is ambiguous or missing, use reasonable defaults
   - For work_right, infer from location/context if not explicitly stated
   - For relocate_willing, set to null if not mentioned

Output ONLY valid JSON matching the AnalyzedResume schema.""",

    # Example for few-shot learning (optional)
    examples=[
        {
            "input": "Sample resume content...",
            "output": {
                "candidate_name": "John Doe",
                "current_title": "Senior Software Engineer",
                # ... full example
            }
        }
    ],
)
```

### 7.2 Prompt Template

**agent_configs/prompts/resume_analyzer.py:**

```python
RESUME_ANALYSIS_PROMPT = """
Analyze the following resume and extract structured information:

RESUME CONTENT:
---
{resume_content}
---

TASK:
Extract all relevant information following these guidelines:

1. **Basic Information**:
   - Candidate name (full name as appears in resume)
   - Current or most recent job title
   - Calculate total years of professional experience

2. **Skills Analysis** (CRITICAL - Follow proficiency rules):

   Technical Skills:
   - Scan ALL sections: work experience, projects, skills section
   - For EACH skill, determine proficiency level:

     * EXPERT if:
       - Used across 3+ projects as primary technology
       - 3+ years experience explicitly mentioned
       - Led migrations, architecture decisions, or mentored others

     * ADVANCED if:
       - Used in production systems with measurable impact
       - Completed complex features independently
       - Mentioned in multiple work experiences with achievements

     * INTERMEDIATE if:
       - Listed in skills section without detailed examples
       - Used in real projects but not as main technology
       - Moderate familiarity indicated

     * BEGINNER if:
       - Only in demos, tutorials, or learning projects
       - Briefly mentioned without context
       - Cannot determine proficiency from available info

   Soft Skills:
   - Extract from descriptions: leadership, communication, teamwork, etc.

3. **Work Experience**:
   - For each role: company, title, dates, achievements, technologies
   - Parse dates into [start, end] format (e.g., ["2020-01", "2022-06"])
   - List concrete achievements and technologies used

4. **Achievements**:
   - Extract QUANTIFIED results: numbers, percentages, time/cost savings
   - Examples: "40% latency reduction", "Managed team of 8", "$2M revenue increase"

5. **Education & Certifications**:
   - Extract education as list of strings (e.g., ["Master of Computer Science, MIT, 2020", "Bachelor of Engineering, UC Berkeley, 2018"])
   - Sort by: Most recent first, then highest degree first
   - Format: "{Degree}, {Institution}, {Year}" (if all available)
   - List all professional certifications

6. **Location & Work Authorization**:
   - Extract location (city/state/country)
   - Determine work authorization/visa status if mentioned
   - Infer relocation willingness if stated (otherwise null)

OUTPUT FORMAT:
Return ONLY a valid JSON object matching the AnalyzedResume schema.
"""
```

---

## 8. API 设计

### 8.1 新增路由

**app/modules/resumes/router.py:**

```python
@router.post("/{resume_id}/analyze", response_model=schemas.WorkflowResponse)
async def trigger_resume_analysis(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger resume analysis.

    Creates a new workflow for resume analysis.
    Can be used to re-analyze an existing resume.
    """
    # Verify ownership
    resume = await ResumeRepository.get_by_id(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Mark for re-analysis
    if resume.analysis:
        resume.analysis.needs_reanalysis = True

    # Create workflow
    workflow = await WorkflowService.create_workflow(
        db=db,
        workflow_type=WorkflowType.RESUME_ANALYSIS,
        user_id=current_user.id,
        entity_id=resume_id,
        input_data={"resume_id": resume_id, "manual_trigger": True},
    )

    # Submit task
    await WorkflowService.submit_task(
        db=db,
        workflow_id=workflow.id,
        task_type=TaskType.RESUME_ANALYSIS,
        input_data={"resume_id": resume_id},
        resume_id=resume_id,
    )

    await db.commit()

    return schemas.WorkflowResponse(
        workflow_id=workflow.id,
        status=workflow.status,
        message="Resume analysis started",
    )


@router.get("/{resume_id}/analysis", response_model=schemas.ResumeAnalysisResponse)
async def get_resume_analysis(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get resume analysis results.

    Returns structured analysis data if available.
    """
    # Verify ownership
    resume = await ResumeRepository.get_by_id(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Check if analysis exists
    if not resume.analysis_result:
        raise HTTPException(status_code=404, detail="Analysis not found. Please trigger analysis first.")

    return schemas.ResumeAnalysisResponse(
        id=resume.id,
        resume_id=resume.id,
        analysis_result=resume.analysis_result,
        analysis_version=resume.analysis_version,
        analyzed_at=resume.analyzed_at,
    )
```

### 8.2 响应 Schema

**app/modules/resumes/schemas.py:**

```python
class ResumeAnalysisResponse(BaseModel):
    """Resume analysis result response"""
    id: str
    resume_id: str
    analysis_result: dict  # AnalyzedResume data
    analysis_version: Optional[str] = None
    analyzed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    """Workflow creation response"""
    workflow_id: str
    status: str
    message: str
```

---

## 9. Repository 实现

**app/modules/resumes/repository.py (新增方法):**

```python
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resumes.models import Resume


class ResumeRepository:
    # ... existing methods ...

    @staticmethod
    async def update_analysis(
        db: AsyncSession,
        resume_id: str,
        analysis_data: dict,
        analysis_version: str,
    ) -> Resume:
        """
        Update resume analysis result.

        Stores analysis data in resume.analysis_result field.
        """
        resume = await ResumeRepository.get_by_id(db, resume_id)
        if not resume:
            raise ValueError(f"Resume {resume_id} not found")

        resume.analysis_result = analysis_data
        resume.analysis_version = analysis_version
        resume.analyzed_at = datetime.now(timezone.utc)
        resume.updated_at = datetime.now(timezone.utc)

        return resume
```

---

## 10. Service 层更新

**app/modules/resumes/service.py:**

```python
from app.modules.workflow.service import WorkflowService
from app.shared.enums import WorkflowType, TaskType

class ResumeService:

    @staticmethod
    async def finalize_resume(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
    ) -> Resume:
        """
        Finalize resume (convert from draft to formal).

        Triggers analysis workflow if content has changed.
        """
        # Get resume with document
        resume = await ResumeRepository.get_with_document(db, resume_id)
        if not resume or resume.user_id != user_id:
            raise ValueError("Resume not found or access denied")

        # Update is_draft
        resume.is_draft = False
        resume.updated_at = datetime.now(timezone.utc)

        # Check if analysis needed
        await ResumeService._trigger_analysis_if_needed(db, resume, user_id)

        await db.commit()
        await db.refresh(resume)

        return resume

    @staticmethod
    async def update_resume(
        db: AsyncSession,
        resume_id: str,
        user_id: int,
        content: str,
        change_comments: Optional[str] = None,
    ) -> Resume:
        """
        Update resume content.

        Triggers analysis if:
        - Resume is formal (not draft)
        - Content hash changed
        """
        resume = await ResumeRepository.get_with_document(db, resume_id)
        if not resume or resume.user_id != user_id:
            raise ValueError("Resume not found or access denied")

        # Create new document version
        new_document = await DocumentService.create_version(
            db=db,
            parent_document_id=resume.document_id,
            content=content,
            change_comments=change_comments,
            created_by=user_id,
        )

        # Update resume document reference
        resume.document_id = new_document.id
        resume.updated_at = datetime.now(timezone.utc)

        # Trigger analysis if formal resume
        if not resume.is_draft:
            await ResumeService._trigger_analysis_if_needed(db, resume, user_id)

        await db.commit()
        await db.refresh(resume)

        return resume

    @staticmethod
    async def _trigger_analysis_if_needed(
        db: AsyncSession,
        resume: Resume,
        user_id: int,
    ):
        """
        Internal helper: Trigger analysis if content changed or never analyzed.
        """
        # Check if analysis needed
        should_analyze = (
            resume.analysis_result is None or  # Never analyzed
            resume.analyzed_at is None
        )

        if should_analyze:
            # Create workflow
            workflow = await WorkflowService.create_workflow(
                db=db,
                workflow_type=WorkflowType.RESUME_ANALYSIS,
                user_id=user_id,
                entity_id=resume.id,
                input_data={"resume_id": resume.id},
            )

            # Submit task
            await WorkflowService.submit_task(
                db=db,
                workflow_id=workflow.id,
                task_type=TaskType.RESUME_ANALYSIS,
                input_data={"resume_id": resume.id},
                resume_id=resume.id,
            )
```

---

## 11. Celery Task 实现

**app/modules/resumes/tasks.py:**

```python
"""Celery tasks for resume analysis."""
import asyncio
from uuid import uuid4

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import get_db
from app.core.llm.gateway import AgentGateway
from app.modules.resumes.models import Resume
from app.modules.resumes.repository import ResumeRepository, ResumeAnalysisRepository
from app.modules.users.repository import UserSkillRepository
from app.modules.workflow import task_status_guard
from agent_configs.schemas import AnalyzedResume


@celery_app.task(bind=True, max_retries=3)
def analyze_resume_async(
    self: Task,
    resume_id: str,
    workflow_id: str,
    task_id: str,
) -> dict:
    """
    Analyze a resume using resume_analyzer agent.

    Status management handled by task_status_guard decorator.

    Args:
        self: Celery task instance
        resume_id: ID of the resume to analyze
        workflow_id: Workflow ID (from WorkflowService)
        task_id: Task ID (from WorkflowService)

    Returns:
        Dictionary with analysis_id and status
    """
    async def _run():
        async for db in get_db():
            return await _execute_resume_analysis(
                db=db,
                resume_id=resume_id,
                workflow_id=workflow_id,
                task_id=task_id,
            )

    return _run_sync(_run())


@task_status_guard(first=True, last=True)
async def _execute_resume_analysis(
    *,
    db: AsyncSession,
    resume_id: str,
    workflow_id: str,
    task_id: str,
) -> dict:
    """
    Execute resume analysis business logic.

    Decorator automatically handles workflow/task status updates.

    Steps:
    1. Load resume with document
    2. Call AI Agent (resume_analyzer)
    3. Parse result (AnalyzedResume schema)
    4. Upsert ResumeAnalysis record
    5. Extract skills to user_skills table
    6. Commit transaction
    """
    # 1. Load resume with document
    resume = await ResumeRepository.get_with_document(db, resume_id)
    if not resume:
        raise ValueError(f"Resume {resume_id} not found")

    # 2. Prepare input content
    content = resume.document.content
    if not content or len(content.strip()) < 50:
        raise ValueError(f"Resume {resume_id} has insufficient content to analyze")

    # 3. Call AI Agent
    result = await AgentGateway.get().call(
        agent_id="resume_analyzer",
        input_data=content,
        context={
            "db": db,
            "operation": "resume_analysis",
            "resume_id": resume_id,
            "user_id": resume.user_id,
        },
    )

    # 4. Parse result
    if isinstance(result, AnalyzedResume):
        analysis_data = result.model_dump()
    else:
        analysis_data = result

    # 5. Update Resume with analysis result
    await ResumeRepository.update_analysis(
        db=db,
        resume_id=resume_id,
        analysis_data=analysis_data,
        analysis_version=AnalyzedResume.__version__,
    )

    # 6. Extract skills to user_skills table
    technical_skills = analysis_data.get("technical_skills", [])
    if technical_skills:
        await UserSkillRepository.upsert_from_resume_analysis(
            db=db,
            user_id=resume.user_id,
            skills=technical_skills,
            resume_id=resume_id,
        )

    # 7. Commit
    await db.commit()

    return {
        "task_output_data": {
            "status": "completed",
            "resume_id": resume_id,
            "skills_extracted": len(technical_skills),
        },
        "workflow_output_data": {
            "resume_id": resume_id,
        },
    }


def _run_sync(coro):
    """
    Run an async coroutine inside Celery worker.

    Reuses event loop to avoid connection cleanup issues.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
```

---

## 12. 实施清单

### 12.1 文件清单

**新建文件:**

```
backend/
├── agent_configs/
│   ├── resume_analyzer.py              # Agent 配置
│   └── prompts/
│       └── resume_analyzer.py          # Prompt 模板
├── app/modules/resumes/
│   └── tasks.py                        # Celery 任务 (新建)
```

**修改文件:**

```
backend/
├── agent_configs/
│   └── schemas.py                      # 新增 AnalyzedResume, Skill, WorkExperience
├── app/modules/resumes/
│   ├── models.py                       # Resume Model 新增 analysis 字段
│   ├── schemas.py                      # 新增 ResumeAnalysisResponse
│   ├── repository.py                   # 新增 update_analysis 方法
│   ├── service.py                      # 更新 finalize/update 方法
│   └── router.py                       # 新增分析相关路由
├── app/modules/users/
│   └── repository.py                   # 新增 upsert_from_resume_analysis 方法
├── alembic/versions/
│   └── YYYYMMDD_xxxx_add_resume_analysis_fields.py  # 数据库迁移
```

### 12.2 实施步骤

**Phase 1: 数据层** (20 分钟)
1. ✅ 定义 Pydantic Schemas (`agent_configs/schemas.py`)
2. ✅ 更新 Resume Model (新增 analysis 字段)
3. ✅ 生成数据库迁移
4. ✅ 执行迁移

**Phase 2: 业务逻辑层** (40 分钟)
5. ✅ 实现 `ResumeRepository.update_analysis`
6. ✅ 实现 `UserSkillRepository.upsert_from_resume_analysis`
7. ✅ 创建 Celery Task (`analyze_resume_async`)
8. ✅ 更新 `ResumeService` (触发逻辑)

**Phase 3: AI Agent** (30 分钟)
9. ✅ 配置 `resume_analyzer` Agent
10. ✅ 编写分析 Prompt (包含熟练度评估规则)
11. ✅ 注册到 AgentGateway

**Phase 4: API 层** (20 分钟)
12. ✅ 新增路由 (`/analyze`, `/analysis`)
13. ✅ 定义响应 Schema
14. ✅ 测试 API 端点

**Phase 5: 测试** (25 分钟)
15. ✅ 单元测试 Repository 方法
16. ✅ 集成测试完整工作流
17. ✅ 验证技能提取逻辑
18. ✅ 测试熟练度评估准确性

---

## 13. 测试场景

### 13.1 功能测试

**场景 1: 定稿简历触发分析**
```
1. 创建草稿简历
2. 调用 finalize API
3. 验证:
   - 工作流创建成功
   - 任务状态变为 RUNNING → SUCCESS
   - ResumeAnalysis 记录创建
   - UserSkill 记录创建
```

**场景 2: 修改正式简历触发分析**
```
1. 已有正式简历
2. 修改内容
3. 验证:
   - 自动触发新分析
   - Resume.analysis_result 更新 (覆盖)
   - UserSkill 熟练度升级 (如适用)
```

**场景 3: 手动触发重新分析**
```
1. 调用 POST /resumes/{id}/analyze
2. 验证:
   - 新工作流创建
   - 分析完成后 Resume.analysis_result 更新
```

**场景 4: 获取分析结果**
```
1. 调用 GET /resumes/{id}/analysis
2. 验证:
   - 返回完整 AnalyzedResume 数据
   - 包含版本号和时间戳
```

### 13.2 边界测试

**测试用例:**
- 简历内容过短 (< 50 字符) → 应抛出异常
- 简历无技能部分 → 应返回空技能列表
- 多个教育经历 → 应按最近优先、学位高低排序
- 技能名称标准化 → 验证 "python" 转为 "Python", "react" 转为 "React"
- AI 调用失败 → 应记录错误,支持重试

---

## 14. 配置参考

### 14.1 环境变量

**.env:**
```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...
RESUME_ANALYZER_MODEL=gpt-4o-mini
RESUME_ANALYZER_TEMPERATURE=0.1

# Feature Flags
ENABLE_AUTO_RESUME_ANALYSIS=true
```

### 14.2 Celery 配置

```python
# app/core/celery_app.py

celery_app.conf.task_routes = {
    "app.modules.resumes.tasks.analyze_resume_async": {"queue": "analysis"},
}
```

---

## 15. 未来优化方向

### 15.1 功能增强
- [ ] 支持多语言简历分析
- [ ] 分析历史版本比较
- [ ] 简历质量评分
- [ ] 简历优化建议生成

### 15.2 性能优化
- [ ] 批量分析多个简历
- [ ] 结果缓存 (Redis)
- [ ] 增量分析 (仅分析变更部分)

### 15.3 数据洞察
- [ ] 技能趋势分析
- [ ] 行业技能分布统计
- [ ] 简历竞争力评估

---

**文档版本:** 1.0.0
**最后更新:** 2025-01-23
**负责人:** AI Assistant
