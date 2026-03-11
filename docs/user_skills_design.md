# 用户技能管理设计文档

**功能模块：** 用户技能提取、管理与职位匹配
**版本：** 1.0
**日期：** 2025-01-23

---

## 1. 需求概述

### 1.1 核心需求

1. **从简历分析中提取技能**
   - 当简历被分析时，提取用户技能并保存
   - 每个技能都有熟练度等级

2. **级联删除**
   - 当简历被删除时，关联的技能应该被移除

3. **手动技能管理**
   - 用户可以手动添加/编辑/删除技能
   - 手动编辑的技能不再与任何简历关联

4. **技能聚合去重**
   - 获取所有用户技能并去重
   - 来自多个简历的技能会被合并
   - 去重优先级：
     - 手动编辑的技能 > 自动提取的技能
     - 高熟练度 > 低熟练度

5. **职位匹配**
   - 分析用户技能与职位要求的匹配度

### 1.2 业务规则

| 规则 | 说明 |
|------|------|
| **多来源** | 同一技能可以出现在多个简历中 |
| **熟练度合并** | 合并时取最高熟练度等级 |
| **手动优先** | 手动编辑的熟练度覆盖自动提取的值 |
| **级联删除** | 删除简历会移除其技能，然后重新聚合 |
| **去重** | 用户技能列表中每个技能只显示一次 |

---

## 2. 数据库设计

### 2.1 表结构总览

```
┌─────────────────────┐         ┌─────────────────────┐
│   resume_skills     │         │    user_skills      │
│  (原始数据)         │────────▶│  (聚合结果)         │
└─────────────────────┘         └─────────────────────┘
         │                               │
         │ FK                            │ FK
         ▼                               ▼
    ┌─────────┐                     ┌─────────┐
    │ resumes │                     │  users  │
    └─────────┘                     └─────────┘
```

### 2.2 表：`resume_skills`

**用途：** 存储从简历分析中提取的原始技能数据

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PRIMARY KEY | 自增ID |
| `user_id` | INT | NOT NULL, FK → users.id | 用户ID |
| `resume_id` | VARCHAR(255) | NOT NULL, FK → resumes.id | 简历ID |
| `skill_name` | VARCHAR(100) | NOT NULL | 技能名称（已规范化） |
| `proficiency_level` | ENUM | NOT NULL | 熟练度：beginner/intermediate/advanced/expert |
| `extracted_from` | JSON | NULL | 可选：记录从简历的哪个部分提取 |
| `created_at` | TIMESTAMP | NOT NULL | 创建时间 |

**索引：**
```sql
INDEX idx_resume_skills_user (user_id, skill_name)
INDEX idx_resume_skills_resume (resume_id)
UNIQUE KEY uk_resume_skill (resume_id, skill_name)
```

**外键：**
```sql
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
```

### 2.3 表：`user_skills`

**用途：** 存储聚合后的用户技能列表（已去重）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PRIMARY KEY | 自增ID |
| `user_id` | INT | NOT NULL, FK → users.id | 用户ID |
| `skill_name` | VARCHAR(100) | NOT NULL | 技能名称（已规范化） |
| `proficiency_level` | ENUM | NOT NULL | 当前有效的熟练度 |
| `is_manual` | BOOLEAN | DEFAULT FALSE | 是否由用户手动编辑 |
| `manual_proficiency` | ENUM | NULL | 用户手动设置的熟练度（如果有） |
| `source_count` | INT | DEFAULT 0 | 有多少个简历提到此技能 |
| `last_seen_at` | TIMESTAMP | NULL | 最后一次在简历中出现的时间 |
| `created_at` | TIMESTAMP | NOT NULL | 创建时间 |
| `updated_at` | TIMESTAMP | NOT NULL | 最后更新时间 |

**索引：**
```sql
UNIQUE KEY uk_user_skill (user_id, skill_name)
INDEX idx_user_skills_proficiency (user_id, proficiency_level)
INDEX idx_user_skills_manual (user_id, is_manual)
```

**外键：**
```sql
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
```

### 2.4 枚举：`ProficiencyLevel`

```python
class ProficiencyLevel(str, Enum):
    BEGINNER = "beginner"           # 初学者 - 权重: 1
    INTERMEDIATE = "intermediate"   # 中级   - 权重: 2
    ADVANCED = "advanced"           # 高级   - 权重: 3
    EXPERT = "expert"               # 专家   - 权重: 4
```

**熟练度权重映射：**
```python
PROFICIENCY_WEIGHTS = {
    ProficiencyLevel.BEGINNER: 1,
    ProficiencyLevel.INTERMEDIATE: 2,
    ProficiencyLevel.ADVANCED: 3,
    ProficiencyLevel.EXPERT: 4,
}
```

---

## 3. 数据流程设计

### 3.1 流程1：简历分析 → 技能提取

```
┌──────────────────────────────────────────────────────────────┐
│ 触发条件：简历分析完成                                         │
└──────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ AI从简历内容中提取技能：      │
        │ [{name, proficiency}, ...]    │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 对每个提取的技能：            │
        │                               │
        │ 1. 规范化技能名称             │
        │    (trim)          │
        │                               │
        │ 2. 检查是否已存在：           │
        │    resume_skills WHERE        │
        │    resume_id=? AND            │
        │    skill_name=?               │
        │                               │
        │ 3. INSERT 或 UPDATE           │
        │    resume_skills   
          4. 删除已经不存在的技能
          delete from resume_skills WHERE resume_id=? AND            │
        │    skill_name not in skill_list   │
                   
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 触发技能聚合                  │
        │ (异步任务或立即执行)          │
        └───────────────────────────────┘
                        │
                        ▼
                 参见流程2
```

### 3.2 流程2：技能聚合（去重）

```
┌──────────────────────────────────────────────────────────────┐
│ 触发条件：简历已分析、已删除或手动触发同步                     │
└──────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 查询 resume_skills：          │
        │                               │
        │ SELECT                        │
        │   skill_name,                 │
        │   MAX(proficiency) as max_p,  │
        │   COUNT(*) as count,          │
        │   MAX(created_at) as last_seen│
        │ FROM resume_skills            │
        │ WHERE user_id = ?             │
        │ GROUP BY skill_name           │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 对每个 skill_name：           │
        │                               │
        │ 检查是否存在于                │
        │ user_skills WHERE             │
        │ user_id=? AND skill_name=?    │
        └───────────────────────────────┘
                        │
                        ├─────────────────────┐
                        │                     │
                ▼ 已存在              ▼ 不存在
        ┌──────────────────┐     ┌──────────────────┐
        │ 如果 is_manual=  │     │ 创建新记录：     │
        │ true:            │     │ • proficiency =  │
        │ • 保留 manual_   │     │   max_p          │
        │   proficiency    │     │ • is_manual=false│
        │ • 保留 prof_level│     │ • source_count=  │
        │ • 更新 source_   │     │   count          │
        │   count          │     │ • last_seen_at=  │
        │ • 更新 last_     │     │   last_seen      │
        │   seen_at        │     └──────────────────┘
        │                  │
        │ 如果 is_manual=  │
        │ false:           │
        │ • 更新 prof_     │
        │   level = max_p  │
        │ • 更新 source_   │
        │   count          │
        │ • 更新 last_     │
        │   seen_at        │
        └──────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 清理孤立技能：                │
        │                               │
        │ DELETE FROM user_skills       │
        │ WHERE user_id = ?             │
        │   AND is_manual = false       │
        │   AND skill_name NOT IN (     │
        │     SELECT DISTINCT skill_name│
        │     FROM resume_skills        │
        │     WHERE user_id = ?         │
        │   )                           │
        └───────────────────────────────┘
                        │
                        ▼
                ┌───────────┐
                │  COMMIT   │
                └───────────┘
```

### 3.3 流程3：删除简历 → 级联清理技能

```
┌──────────────────────────────────────────────────────────────┐
│ 触发条件：用户删除简历 (resume_id)                            │
└──────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 数据库级联删除：              │
        │                               │
        │ DELETE FROM resume_skills     │
        │ WHERE resume_id = ?           │
        │                               │
        │ (由 ON DELETE CASCADE         │
        │  外键自动触发)                │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 应用层触发器：                │
        │                               │
        │ 在删除简历后：                │
        │ • 将异步任务加入队列：        │
        │   aggregate_user_skills(      │
        │     user_id=user_id           │
        │   )                           │
        └───────────────────────────────┘
                        │
                        ▼
                 参见流程2
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 结果：                        │
        │                               │
        │ • 仅存在于已删除简历的技能    │
        │   会从 user_skills 移除       │
        │   (如果不是手动的)            │
        │                               │
        │ • 其他简历中的技能保留，      │
        │   source_count 会更新         │
        │                               │
        │ • 手动技能始终保留            │
        └───────────────────────────────┘
```

### 3.4 流程4：用户手动编辑技能

```
┌──────────────────────────────────────────────────────────────┐
│ 用户操作：手动添加/编辑/删除技能                              │
└──────────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
    ┌───────┐     ┌─────────┐     ┌────────┐
    │  添加 │     │  编辑   │     │  删除  │
    └───────┘     └─────────┘     └────────┘
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ INSERT INTO  │ │ UPDATE       │ │ DELETE FROM  │
│ user_skills: │ │ user_skills  │ │ user_skills  │
│              │ │ SET:         │ │ WHERE id=?   │
│ • user_id    │ │ • is_manual  │ │ AND user_id=?│
│ • skill_name │ │   = true     │ │              │
│ • proficiency│ │ • manual_    │ │ (仅从 user_  │
│   _level     │ │   proficiency│ │  skills 删除 │
│ • is_manual  │ │   = new_val  │ │  不影响      │
│   = true     │ │ • proficiency│ │  resume_     │
│ • manual_    │ │   _level     │ │  skills)     │
│   proficiency│ │   = new_val  │ └──────────────┘
│   = input    │ │ • updated_at │
│ • source_    │ │              │
│   count = 0  │ │ WHERE id=?   │
│              │ │ AND user_id=?│
│ (不影响      │ └──────────────┘
│  resume_     │
│  skills)     │
└──────────────┘
```

### 3.5 流程5：获取用户所有技能（已去重）

```
┌──────────────────────────────────────────────────────────────┐
│ API: GET /api/v1/skills                                       │
└──────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 查询 user_skills：            │
        │                               │
        │ SELECT * FROM user_skills     │
        │ WHERE user_id = ?             │
        │ ORDER BY                      │
        │   proficiency_level DESC,     │
        │   skill_name ASC              │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 返回：                        │
        │                               │
        │ [{                            │
        │   id: 1,                      │
        │   skill_name: "Python",       │
        │   proficiency_level: "expert",│
        │   is_manual: true,            │
        │   source_count: 3,            │
        │   last_seen_at: "2025-01-20"  │
        │ }, ...]                       │
        └───────────────────────────────┘
```

### 3.6 流程6：技能与职位匹配

```
┌──────────────────────────────────────────────────────────────┐
│ API: POST /api/v1/skills/match/{job_id}                      │
└──────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 1. 获取职位要求的技能         │
        │    (从 job_analysis.skills    │
        │     或 job_skills 表)         │
        │                               │
        │ 2. 获取用户技能               │
        │    (从 user_skills)           │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 3. 计算匹配度：               │
        │                               │
        │ matched_skills = []           │
        │ missing_skills = []           │
        │ proficiency_gaps = []         │
        │                               │
        │ for req_skill in job_skills:  │
        │   user_skill = find(req_skill)│
        │   if user_skill:              │
        │     matched_skills.append()   │
        │     if user_prof < req_prof:  │
        │       proficiency_gaps.append │
        │   else:                       │
        │     missing_skills.append()   │
        │                               │
        │ match_score = (               │
        │   matched_count /             │
        │   total_required              │
        │ ) * 100                       │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 返回：                        │
        │ {                             │
        │   match_score: 85,            │
        │   matched_skills: [           │
        │     {name, user_prof, req_prof│
        │      match_quality}           │
        │   ],                          │
        │   missing_skills: [...],      │
        │   proficiency_gaps: [...]     │
        │ }                             │
        └───────────────────────────────┘
```

---

## 4. API 设计

### 4.1 端点列表
router 放在users模块下

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| `GET` | `/api/v1/skills` | 获取用户所有技能（已去重） | 必需 |
| `POST` | `/api/v1/skills` | 手动添加新技能 | 必需 |
| `PUT` | `/api/v1/skills/{skill_id}` | 编辑技能熟练度 | 必需 |
| `DELETE` | `/api/v1/skills/{skill_id}` | 删除技能 | 必需 |
| `POST` | `/api/v1/skills/sync` | 触发技能聚合（管理/调试用） | 必需 |

### 4.2 请求/响应示例

#### GET `/api/v1/skills`

**响应：**
```json
{
  "items": [
    {
      "id": 1,
      "skill_name": "Python",
      "proficiency_level": "expert",
      "is_manual": true,
      "source_count": 3,
      "last_seen_at": "2025-01-20T10:30:00Z",
      "created_at": "2025-01-01T08:00:00Z",
      "updated_at": "2025-01-20T10:30:00Z"
    }
  ],
  "total": 15,
  "manual_count": 5,
  "auto_count": 10
}
```

#### POST `/api/v1/skills`

**请求：**
```json
{
  "skill_name": "Docker",
  "proficiency_level": "advanced"
}
```

**响应：**
```json
{
  "id": 16,
  "skill_name": "Docker",
  "proficiency_level": "advanced",
  "is_manual": true,
  "source_count": 0,
  "created_at": "2025-01-23T14:00:00Z"
}
```

#### PUT `/api/v1/skills/{skill_id}`

**请求：**
```json
{
  "proficiency_level": "expert"
}
```

**响应：**
```json
{
  "id": 16,
  "skill_name": "Docker",
  "proficiency_level": "expert",
  "is_manual": true,
  "updated_at": "2025-01-23T15:00:00Z"
}
```

---

## 5. 业务逻辑

### 5.1 技能名称规范化

**规则：** 技能名称由ai分析并规范化，代码不需要处理

### 5.2 熟练度比较

```python
def compare_proficiency(level1: ProficiencyLevel, level2: ProficiencyLevel) -> int:
    """
    Compare two proficiency levels
    Returns: -1 (level1 < level2), 0 (equal), 1 (level1 > level2)
    """
    weight1 = PROFICIENCY_WEIGHTS[level1]
    weight2 = PROFICIENCY_WEIGHTS[level2]

    if weight1 < weight2:
        return -1
    elif weight1 > weight2:
        return 1
    else:
        return 0
```

### 5.3 技能聚合算法

**核心逻辑：**

```python
async def aggregate_user_skills(
    db: AsyncSession,
    user_id: int,
    affected_skill_names: Optional[List[str]] = None
) -> None:
    """
    Aggregate user skills from resume_skills to user_skills

    Args:
        db: Database session
        user_id: User ID
        affected_skill_names: Optional list of skill names to update (incremental)
    """
    # Step 1: Query resume_skills aggregated by skill_name
    query = (
        select(
            ResumeSkill.skill_name,
            func.max(ResumeSkill.proficiency_level).label('max_proficiency'),
            func.count().label('source_count'),
            func.max(ResumeSkill.created_at).label('last_seen_at')
        )
        .where(ResumeSkill.user_id == user_id)
        .group_by(ResumeSkill.skill_name)
    )

    if affected_skill_names:
        query = query.where(ResumeSkill.skill_name.in_(affected_skill_names))

    result = await db.execute(query)
    resume_skills_agg = result.all()

    # Step 2: Update or create user_skills
    for skill_name, max_prof, count, last_seen in resume_skills_agg:
        stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.skill_name == skill_name
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            # Update existing skill
            if existing.is_manual:
                # Manual skill: only update metadata, keep proficiency
                existing.source_count = count
                existing.last_seen_at = last_seen
            else:
                # Auto skill: update proficiency and metadata
                existing.proficiency_level = max_prof
                existing.source_count = count
                existing.last_seen_at = last_seen

            existing.updated_at = datetime.utcnow()
        else:
            # Create new skill
            new_skill = UserSkill(
                user_id=user_id,
                skill_name=skill_name,
                proficiency_level=max_prof,
                is_manual=False,
                source_count=count,
                last_seen_at=last_seen
            )
            db.add(new_skill)

    # Step 3: Clean up orphaned skills (only if full sync, not incremental)
    if not affected_skill_names:
        all_resume_skill_names = {row[0] for row in resume_skills_agg}

        stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.is_manual == False,
            UserSkill.skill_name.notin_(all_resume_skill_names)
        )
        orphaned_skills = (await db.execute(stmt)).scalars().all()

        for skill in orphaned_skills:
            await db.delete(skill)

    await db.commit()
```
---

## 6. 实施计划

### 阶段1：数据库搭建

**任务：**
1. 在 `app/shared/enums.py` 中创建 `ProficiencyLevel` 枚举
2. 在 `app/modules/resumes/models.py` 中创建 `ResumeSkill` 模型
3. 在 `app/modules/users/models.py`中创建 `UserSkill` 模型
4. 创建 Alembic 迁移
5. 运行迁移

**涉及文件：**
- `backend/app/shared/enums.py`（更新）
- `backend/app/modules/resumes/models.py`（更新）
- `backend/app/modules/users/models.py`（更新）

### 阶段2：技能模块后端

**任务：**
1. 实现 `SkillService` 包含聚合逻辑，放入文件 users/service.py
2. 创建 Pydantic schemas
3. 实现 API router
4. 在 API v1 中注册路由

**涉及文件：**
- `backend/app/modules/users/models.py`
- `backend/app/modules/users/schemas.py`
- `backend/app/modules/users/service.py`
- `backend/app/modules/users/router.py`

### 阶段3：简历分析集成

**任务：**
1. 更新简历分析流程以提取技能
2. 将提取的技能保存到 `resume_skills` 表
3. 分析后触发技能聚合
4. 更新简历删除处理器以触发重新聚合

**涉及文件：**
- `backend/app/modules/resumes/service.py`（更新）
- 简历分析工作流（更新）

### 阶段4：前端实现

**任务：**
1. 创建技能 API 客户端
2. 创建 `useSkills` hook
3. 构建技能管理页面/组件

**涉及文件：**
- `frontend/src/api/skills.ts`（新建）
- `frontend/src/features/users/hooks/useSkills.ts`（新建）
- `frontend/src/features/users/components/SkillsList.tsx`（新建）

### 阶段5：测试与文档

**任务：**
1. 测试从简历提取技能
2. 测试聚合逻辑
3. 测试级联删除
4. 测试手动技能管理
5. 测试匹配分数计算
6. 更新 API 文档

---

## 7. 边界情况与考量

### 7.1 边界情况

| 情况 | 处理方式 |
|------|---------|
| **用户删除所有包含某技能的简历，然后手动添加该技能** | 技能保留，`is_manual=true` |
| **同一技能在2个简历中，熟练度不同** | 取最高熟练度，任一简历删除时更新 |
| **用户手动设置的熟练度低于自动提取的** | 手动值优先，自动值被忽略 |
| **技能名称的变体** | 规范化名称；未来：模糊匹配/技能同义词 |
| **简历重新分析改变技能熟练度** | 更新 `resume_skills`，触发聚合，可能更新 `user_skills`（如果不是手动的） |

### 7.2 性能考量

1. **聚合频率**
   - 方案A：每次简历分析/删除后实时聚合（较慢，始终最新）
   - 方案B：异步任务队列（较快，最终一致性）
   - **推荐：** 异步任务，更好的用户体验

2. **索引**
   - 索引 `(user_id, skill_name)` 用于快速查找
   - 索引 `resume_id` 用于级联删除
   - 索引 `(user_id, proficiency_level)` 用于排序

3. **缓存**
   - 缓存用户技能列表（更新时失效）
   - 缓存职位匹配分数（技能更新时失效）

### 7.3 未来增强

1. **技能分类**
   - 技能类别（编程语言、框架、工具等）
   - 技能同义词（JavaScript = JS, React.js = React）
   - 技能层级（React → 前端 → Web开发）

2. **技能验证**
   - 链接到证书
   - 背书（如果是多用户系统）
   - 自我评估 vs 已验证技能

3. **高级匹配**
   - 职位中技能的加权重要性
   - 必需 vs 加分技能
   - 技能组合/协同评分

4. **技能趋势**
   - 跟踪技能熟练度随时间的变化
   - 技能变更的版本历史
   - 技能增长建议

---

## 8. 迁移策略

### 8.1 向后兼容性

- 没有分析的现有简历：无影响
- 新分析：自动填充技能
- 旧分析结果：可重新处理以提取技能

### 8.2 数据迁移

如果用户已有带分析结果的简历：

```python
# Migration script
async def backfill_skills_from_existing_resumes():
    """
    Extract skills from existing resume analysis results
    """
    resumes_with_analysis = await db.execute(
        select(Resume).where(Resume.analysis_result.isnot(None))
    )

    for resume in resumes_with_analysis.scalars():
        # Extract skills from analysis_result JSON
        skills = extract_skills_from_analysis(resume.analysis_result)

        # Save to resume_skills
        for skill in skills:
            resume_skill = ResumeSkill(
                user_id=resume.user_id,
                resume_id=resume.id,
                skill_name=normalize_skill_name(skill["name"]),
                proficiency_level=skill["proficiency"]
            )
            db.add(resume_skill)

    await db.commit()

    # Trigger aggregation for all users
    user_ids = await db.execute(select(Resume.user_id).distinct())
    for user_id in user_ids.scalars():
        await aggregate_user_skills(db, user_id)
```

---

## 9. 安全考量

1. **授权**
   - 用户只能访问/修改自己的技能
   - 所有查询中检查 `user_id`

2. **输入验证**
   - 验证 skill_name 长度和格式
   - 验证 proficiency_level 是有效的枚举值
   - 通过参数化查询防止 SQL 注入

3. **速率限制**
   - 限制手动技能添加/编辑操作（例如：100次/天）
   - 防止滥用匹配分数 API

---

## 10. 测试策略

### 10.1 单元测试

- `test_normalize_skill_name()`
- `test_compare_proficiency()`
- `test_aggregate_user_skills()`
- `test_calculate_match_score()`

### 10.2 集成测试

- 测试 简历分析 → 技能提取 → 聚合 流程
- 测试 简历删除 → 级联删除 → 重新聚合
- 测试 手动技能 CRUD 操作
- 测试 职位匹配 API

### 10.3 测试场景

1. **场景：新用户，第一份简历**
   - 分析简历 → 提取5个技能 → 验证 user_skills 有5条记录

2. **场景：第二份简历有重叠技能**
   - 分析第2份简历，包含3个新技能 + 2个已存在技能
   - 验证 user_skills 共8个（3+5），重叠技能取最高熟练度

3. **场景：删除第一份简历**
   - 删除简历 → 验证其独有技能被移除
   - 验证重叠技能保留，熟练度来自第2份简历

4. **场景：手动编辑**
   - 用户手动设置 Python 为 "expert"
   - 分析新简历，Python="intermediate"
   - 验证 user_skills 保持 "expert"（手动优先）

5. **场景：职位匹配**
   - 用户拥有：Python(expert), JavaScript(advanced), React(intermediate)
   - 职位要求：Python(advanced), JavaScript(expert), React(intermediate), Docker(intermediate)
   - 预期：75% 匹配（3/4），1个熟练度差距（JavaScript），1个缺失（Docker）

---

**文档结束**
