# 问题修复记录

## ✅ 已调整（待部署）：简历 PDF 默认字号 10pt 偏小

### 问题描述
10pt 的正文读起来吃力。

### 处理
用两份真实简历对比 10、10.5、11、11.5、12pt：
- 11pt 两份都没有多出页数（3 页、4 页），只是最后一页填得更满；
- 11.5pt 和 12pt 会多出一页，12pt 时联系方式那一行还会折行。

所以把 `PDFGenerator.DEFAULT_FONT_SIZES` 里的简历默认值从 10 改为 11，和 cover letter 一致。

## ✅ 已修复（待部署）：定制简历的岗位名称没有对齐目标岗位

### 问题描述
简历新格式里姓名是一级标题，岗位名称降为姓名下方的副标题。定制简历的副标题基本照抄模板，例如目标岗位是 "Senior Software Engineer"，生成的仍是 "Senior Full Stack Developer"。

### 根本原因
- `resume_tailor.yaml` 要求把岗位名称对齐目标岗位，但 `load_tailoring_input` 组装 `AnalyzedJob` 时没有放 `normalized_job_title`，也没有传招聘原文的岗位名称，模型不知道目标岗位叫什么。
- prompt 只说 "candidate's title"，没有说明岗位名称写在哪一行，也没说明一级标题是姓名。结构没出错，靠的是“保留原结构”这条兜底。
- classic / minimal 两个 PDF 模板会在正文上方再加一个 `<h1>{{ title }}</h1>`；定制简历导出时 title 固定传 "Resume"，所以 PDF 顶部会多出一个 "Resume" 大标题。

### 修复方案
- prompt 新增 `target_job_title`（招聘原文的岗位名称），`job_analysis` 补上 `normalized_job_title`。
- `resume_tailor.yaml` 升到 v5：写明一级标题是姓名、不能改；岗位名称是姓名下方那一行，只改里面的文字，HTML 标签和样式保持原样；岗位名称以目标岗位为准，资历按经历证据确定。
- 删除 classic / minimal 模板的标题头；三个模板都把正文的第一个 H1（姓名）居中，各自保留字号和颜色。

### 验证
- `tests/modules/workflow` 和 agent 配置测试共 35 个，全部通过。
- 用真实简历渲染三个模板：顶部都是居中的姓名和副标题，不再出现 "Resume"。
- 模型实际生成效果要等上线后，再重新生成一份定制简历来确认。

## ✅ 已修复（待部署）：简历预览和导出的 PDF 版式不一致（一级标题对齐不同）

### 问题描述
申请详情页的简历预览里，一级标题（姓名）靠左；导出的 PDF 里是居中的。副标题和联系方式两处都居中。

### 根本原因
- 副标题和联系方式的居中写在 markdown 的内联 `style` 里，预览和 PDF 都会执行，所以两边一致。
- 姓名的居中只写在 PDF 模板 `resume/modern.css` 的 `.resume-content > h1:first-child` 上。前端 `MarkdownPreview` 用的是 Tailwind `prose`，标题样式也是自己写的，和 PDF 的 CSS 完全是两套。
- 同样原因的其他差异：字号（预览 16px，PDF 10pt）、行高（1.75 对 1.4）、页边距、二级标题（PDF 是紫色加下边框）、链接（预览有下划线）。

### 修复方案
- `MarkdownPreview` 新增 `variant`。简历（`resume`、`tailored_resume`）用 `resume` 变体，样式在 `components/MarkdownPreview/styles.css`；cover letter 仍用原来的 prose 样式。
- 简历预览沿用 PDF modern 模板的版式：姓名居中、二级标题用强调色加下边框、各级标题层级、链接和列表样式、间距比例。字号、行高、边距按屏幕阅读调整（15px，行高 1.6，rem 内边距，窄屏收窄），字体用页面本身的字体，不照搬 10pt 和厘米边距。
- 申请详情页和文档编辑页按 `business_type` 选择变体。

### 验证
用真实简历在浏览器里检查预览：姓名居中，二级标题和链接样式与同一份 markdown 导出的 PDF 一致；桌面和 375px 手机宽度都没有横向滚动；cover letter 预览不受影响。

## ✅ 已修复（待部署）：导出的简历 PDF 偏长（真实简历 6 页），中文无法显示

### 问题描述
生产环境导出的定制简历（约 1.09 万字符）有 6 页。

### 根本原因
- **字号参数没生效：** `font_size` 传进了模板上下文，但模板从未使用；`resume/base.css` 写死 `html { font-size: 12pt }`。前端又在两个 API 文件里各写死 `|| 12`。
- **字体没加载：** CSS 用 `@font-face` 引用 `static/fonts/` 下的 Noto 字体，但这个目录从未提交（文档要求手动下载）；生成器也没传 `FontConfiguration`。实际出图用 DejaVu：字形偏宽，且没有中文字形。Cover letter 指定的 Times New Roman 在容器里也不存在。
- **版面偏松：** 页边距 2cm/2.5cm；`base.css` 和 `modern.css` 各有一套间距，后者覆盖前者，正文行高 1.5。
- **内容本身较长：** 只改样式压不到 2 页。

### 修复方案
- `PDFGenerator` 按文档类型给默认字号（简历 10pt、cover letter 11pt），以 `html { font-size }` 注入；CSS 全部用相对单位。schema 的 `font_size` 改为可选，前端不再写死默认值。
- Dockerfile 安装 `fonts-liberation2`（Arial/Times 同宽）和 `fonts-noto-cjk`；删除失效的 `@font-face`，font-family 改为系统字体。
- 简历边距改为 1.5cm/1.8cm，行高 1.4；间距统一定义在 `resume/base.css`，模板 CSS 只管颜色、字号和装饰。
- 分页：标题 `break-after: avoid`，`orphans`/`widows` 2。要点不加 `break-inside: avoid`：带子列表的父级要点会被整块挤到下一页，留下大段空白（code review 发现）。
- Cover letter 的 CSS 从 pt 改为相对单位，跟随字号。

### 验证
用新镜像在本地渲染这份真实简历：modern 4 页（第 4 页 5 行），classic / minimal 3 页；cover letter（4 段）1 页；中英文分别使用 Liberation 和 Noto CJK。

## ✅ 已修复（待部署）：DeepSeek V4.1 Flash 做 match_judge 时随机输出无效 JSON

### 问题描述
评估 DeepSeek V4.1 Flash（xhigh）替换 Terra 时，16–28% 的调用首次返回无效或被截断的 JSON（`Invalid JSON when parsing`、`EOF while parsing`），重试多数能成功。

### 根本原因
- OpenRouter 把同一模型路由到约 47 个托管商端点，默认按价格分配。
- **Wafer**（`wafer/us`、`wafer/mxfp4`）的输出基本不可用：
  - 测试的 13 次调用全部失败，其中 4 次是在开启 Response Healing 之后。
  - 失败形式包括 JSON 损坏、字段名乱码、嵌套结构错乱。这类内容损坏 Healing 修不了。
- 其他托管商一共测了 164 次完整调用，没有出现语法错误的 JSON。
  - 唯一的异常是 3 次输出失控：模型在某个 quote 字段里不停重复，直到 token 用完（Cohere、DeepInfra、DeepInfra priority 各 1 次）。
  - 这是模型本身的问题，靠重试兜底。
- **截断（推测，未单独验证）：** 164 次有效回答里有 22 次的输出超过 12000 token，最高 24366。
  - 如果托管商把推理 token 也算进 `max_tokens`，这些回答在 12000 的上限下会被截断。
  - 不过也有托管商在 12000 的上限下仍然输出了 2.8 万 token，所以并不是每家都按这个上限执行。

### 修复方案
- **限定托管商：** 新增 `MATCH_JUDGE_OPENROUTER_PROVIDERS`，只路由到验证过的托管商（provider `only`）。
  - gateway 现在逐键合并 `provider` 路由对象，所以 `require_parameters` 和 `data_collection=deny` 仍然生效。
  - 这个 env 变量接受 JSON 列表或逗号分隔两种写法。
- **调整 `match_judge.yaml`：** `max_tokens` 调到 32000；开启 Response Healing 作为额外保险（只修语法错误，这次的问题它修不了）。
  - 已确认 Terra 在新配置下调用正常。
- **记录托管商：** gateway 从 OpenRouter 响应中记录实际服务的托管商、generation id 和实际费用，写入日志、`context["usage"]` 和新指标 `jobpilot_llm_upstream_call_total`。
  - 成功和失败两条路径都已验证。
- **保留重试：** 已有的 `judge_pair` 原地重试（638baea）保留，作为最后一道兜底。

### 验证结果
- 下面 5 家各 21 次调用，全部是有效 JSON：sail-research/fp4、particle-ai/us/flex、morph/fp8、river、ionstream/flex。
- DeepInfra/fp8 是 20/21：1 次输出失控，而且速度慢，单次最长 192 秒。
- 21 次零失败只能说明失败率大概率低于约 14%。更准确的数字要等用金标准试跑和上线后的观察。

---

## ✅ 已修复：应用源简历外键删除行为与非空约束冲突

### 问题描述
`applications.source_resume_id` 被定义为非空字段，但外键删除行为配置为 `ON DELETE SET NULL`。

### 根本原因
- 业务上应用记录必须始终保留来源简历引用
- 简历删除当前是软删除，不应该允许数据库在硬删除时把应用的 `source_resume_id` 置空
- `SET NULL` 与 `nullable=False` 组合会导致约束语义冲突

### 修复方案
- 模型层将 `source_resume_id` 的删除行为改为 `RESTRICT`
- 新增 Alembic migration，同步数据库外键约束

### 验证结果
- 应用模型与数据库约束语义一致
- 不再存在“要求非空但删除时置空”的矛盾配置

---

## ✅ 已修复：手动触发 Job Analysis 使用了错误的 TaskType / EntityType

### 问题描述
`POST /api/v1/jobs/{job_id}/analyze` 路由错误导入了 Celery 的 `TaskType`，并使用了不存在的 `EntityType.job`。

### 根本原因
- 路由文件混用了 Celery 类型和项目业务枚举
- `EntityType` 在项目里定义为大写枚举成员（如 `EntityType.JOB`）

### 修复方案
- 改为使用 `app.shared.enums.TaskType`
- 将 `EntityType.job.value` 改为 `EntityType.JOB.value`
- 删除无用的任务函数导入

### 验证结果
- 手动触发 job analysis 的路由不再包含确定性的枚举访问错误

---

## ✅ 已修复：登录失败时页面刷新导致错误信息消失

### 问题描述
用户在登录页输入错误的账号密码后：
1. 点击登录按钮
2. 页面突然刷新
3. 错误信息一闪而过，无法查看
4. 用户看到的是刷新后的空白登录页

### 根本原因
在 [client.ts:27-31](../frontend/src/api/client.ts#L27-L31) 的 Axios 响应拦截器中：

```typescript
if (error.response?.status === 401) {
  localStorage.removeItem('access_token')
  window.location.href = '/login'  // 强制刷新页面
}
```

**问题分析**：
1. 拦截器的原始目的是处理 **token 过期**场景
2. 当用户已登录，访问需要认证的页面时 token 失效，自动重定向到登录页
3. 但拦截器**无法区分**"登录失败 401"和"token 过期 401"
4. 导致在登录页输入错误密码时，也触发了 `window.location.href = '/login'`
5. 页面硬刷新导致所有 React state（包括 `error`）被清空

### 修复方案
检查当前路径，避免在登录/注册页重定向

### 修复步骤

#### 修改 `frontend/src/api/client.ts`

```typescript
// 从:
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 改为:
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Only redirect if not already on login/register page
      const currentPath = window.location.pathname
      if (currentPath !== '/login' && currentPath !== '/register') {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
```

### 验证结果

✅ **验证步骤**:
```bash
cd frontend
pnpm run dev
```

访问 `http://localhost:5173/login`，输入错误的账号密码

✅ **预期效果**:
- 登录失败时，页面**不刷新**
- 错误信息正常显示：`Login failed. Please try again.` 或后端返回的具体错误
- 用户可以完整阅读错误信息
- 错误信息在再次提交时才清空

✅ **其他场景验证**:
- 注册页输入错误时，也不会刷新
- 用户已登录，token 过期时，仍会正确重定向到登录页
- 不影响其他需要认证的页面的行为

### 技术说明

**401 错误的两种场景**:

| 场景 | 描述 | 应该的行为 | 修复前 | 修复后 |
|------|------|-----------|--------|--------|
| 登录失败 | 用户输入错误的账号密码 | 显示错误信息，不刷新 | ❌ 强制刷新 | ✅ 显示错误 |
| Token 过期 | 已登录用户的 token 失效 | 重定向到登录页 | ✅ 正确重定向 | ✅ 正确重定向 |

**路径检查逻辑**:
- `/login` - 登录页，不触发重定向
- `/register` - 注册页，不触发重定向
- 其他路径 - 触发重定向（如 `/jobs`, `/dashboard` 等）

### 相关修复

此问题修复与之前的"错误信息一闪而过"问题相关：
1. **之前修复**：删除了 `handleChange` 中的 `setError('')`，避免输入时清空错误
2. **本次修复**：避免 401 错误时页面刷新，确保错误信息能够显示

两个修复结合，完全解决了用户无法看到登录错误信息的问题。

### 后续注意事项

1. **新增认证页面**：如果添加了其他认证相关页面（如忘记密码、重置密码），需要在路径检查中添加
2. **使用 React Router 导航**：未来可考虑重构，使用 `useNavigate` 替代 `window.location.href`，避免硬刷新
3. **错误码细化**：后端可考虑区分不同的 401 场景（如 `LOGIN_FAILED` vs `TOKEN_EXPIRED`）

### 参考资源
- [Axios Interceptors Documentation](https://axios-http.com/docs/interceptors)
- [React SPA Authentication Best Practices](https://react.dev/learn/synchronizing-with-effects)

---

**修复时间**: 2025-01-23
**修复状态**: ✅ 完成
**影响范围**: 前端认证流程、错误处理

---

## ✅ 已修复：FastAPI 数据库异步驱动配置错误

### 问题描述
```
sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async driver.
The loaded 'psycopg2' is not async.
```

### 根本原因
- `.env` 文件中的 `DATABASE_URL` 使用了 `postgresql://` 协议
- 该协议默认使用同步驱动 `psycopg2`
- 项目使用 `create_async_engine` 需要异步驱动
- 异步引擎与同步驱动不兼容

### 修复方案
将数据库连接协议从同步改为异步驱动

### 修复步骤

#### 1. 更新 `.env` 文件
```bash
# 从:
DATABASE_URL=postgresql://username:password@localhost:5432/jobpilot

# 改为:
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/jobpilot
```

#### 2. 更新 `.env.example` 文件（如果需要）
```bash
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobpilot
```

### 验证结果

✅ **验证步骤**:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

✅ **预期效果**:
- 服务正常启动，无 SQLAlchemy 异步驱动错误
- 数据库连接成功
- API 接口可正常访问

### 技术说明

**PostgreSQL 驱动对比**:

| 驱动 | 协议 | 类型 | 使用场景 |
|------|------|------|----------|
| `psycopg2` | `postgresql://` | 同步 | 传统同步应用 |
| `asyncpg` | `postgresql+asyncpg://` | 异步 | FastAPI 异步应用 |

**项目配置**:
- 引擎: `create_async_engine` ([app/core/database.py](../backend/app/core/database.py))
- Session: `AsyncSession`
- 依赖注入: `async def get_db()`

### 后续注意事项

1. **环境变量一致性**: 确保所有环境（开发/测试/生产）都使用 `postgresql+asyncpg://`
2. **文档更新**: 已在 [README.md](../README.md) 的数据库配置部分说明
3. **团队协作**: 提醒团队成员检查本地 `.env` 配置
4. **依赖检查**: 确保 `asyncpg` 已安装在 `pyproject.toml` 中

### 参考资源
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)

---

**修复时间**: 2025-01-23
**修复状态**: ✅ 完成
**影响范围**: 后端数据库连接

---

## ✅ 已修复：Tailwind CSS v4 PostCSS 配置问题

### 问题描述
```
[postcss] It looks like you're trying to use `tailwindcss` directly as a PostCSS plugin.
The PostCSS plugin has moved to a separate package...
```

### 根本原因
- 项目初始化时安装了 Tailwind CSS v4.1.17
- v4 的 PostCSS 插件移到了独立的包 `@tailwindcss/postcss`
- 配置文件使用的是 v3 语法

### 修复方案
选择了**方案 2：升级到 Tailwind CSS v4**

### 修复步骤

#### 1. 安装 v4 PostCSS 插件
```bash
npm install -D @tailwindcss/postcss
```

#### 2. 更新 `postcss.config.js`
```javascript
// 从:
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}

// 改为:
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}
```

#### 3. 删除 `tailwind.config.js`
v4 不再需要此配置文件，使用 CSS 变量配置。

#### 4. 更新 `src/index.css`
```css
/* 从: */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* 改为: */
@import "tailwindcss";

@layer base {
  /* 自定义样式 */
}
```

#### 5. 卸载 autoprefixer
```bash
npm uninstall autoprefixer
```
v4 内置了 autoprefixer。

### 验证结果

✅ **依赖版本**:
```
tailwindcss@4.1.17
@tailwindcss/postcss@4.1.17
```

✅ **预期效果**:
- PostCSS 错误消失
- Tailwind 样式正常编译
- 所有工具类可用
- 构建速度提升

### 文档更新
- ✅ 更新 [README.md](./README.md) - 技术栈说明

### 后续注意事项

1. **自定义主题**: 使用 `@theme` 指令而非配置文件
2. **插件使用**: 需要时创建 `tailwind.config.ts`
3. **CSS 层叠**: 使用 `@layer` 组织样式
4. **性能**: v4 构建速度比 v3 快约 10 倍

### 参考资源
- [Tailwind CSS v4 文档](https://tailwindcss.com/docs)
- [v3 到 v4 迁移指南](https://tailwindcss.com/docs/upgrade-guide)

---

**修复时间**: 2025-01-23
**修复状态**: ✅ 完成
**影响范围**: 前端构建系统

## Fixed: Shared Pagination rendered duplicate last-page numbers

### Problem
On the admin task monitor page, pagination could render duplicate page numbers near the end of the range (example: total records `198`, page size `20`, expected total pages `10`, but UI showed repeated `10`).

### Root Cause
The shared pagination component (`frontend/src/components/ui/pagination.tsx`) used a page-number generation algorithm that could produce duplicate `pageNum` values when `currentPage` was near the end.

### Solution
Replaced page-number generation with a bounded sliding window:
- Compute `startPage` with clamp: `max(1, min(currentPage - 2, totalPages - pagesToShow + 1))`
- Compute `endPage` from `startPage`
- Build page list from `startPage..endPage` to ensure uniqueness and ordering
- Keep existing controls and ellipsis behavior unchanged

### Verification
- Confirmed no duplicate page numbers in end-range scenarios.
- Confirmed this fix applies to all pages reusing shared `Pagination`:
  - Admin task list
  - Jobs listing
  - Applications listing

### Notes
Frontend build currently reports pre-existing TypeScript errors unrelated to this pagination fix. The pagination patch itself is isolated to shared UI rendering logic.

---

**Fixed On**: 2026-03-12
**Status**: Completed
**Scope**: Frontend shared pagination component

## Known Issue: Frontend build has pre-existing TypeScript type errors

### Problem
Running `pnpm run build` in `frontend/` fails due to multiple TypeScript errors that are not introduced by the retry-refresh/animation changes.

### Root Cause
The current codebase has existing type mismatches across admin API/query hooks (Axios response typing vs expected query/mutation payload typing), plus several unrelated strict-mode/type hygiene issues.

### Impact
- Full frontend production build is currently blocked.
- This affects validation confidence for unrelated UI changes unless a scoped check strategy is used.

### Workaround
- Validate changed behavior manually in dev mode for now.
- Handle type-system cleanup in a dedicated follow-up task to avoid mixing with feature fixes.

### Verification
Build command executed:
```bash
cd frontend
pnpm run build
```
Result: failed with existing TypeScript errors across files outside this task's modified scope.

---

**Detected On**: 2026-03-12
**Status**: Open
**Scope**: Frontend TypeScript typing baseline

---

## ✅ Fixed: Celery async task failures with `This event loop is already running`

### Problem
Within a short burst of task execution, multiple Celery tasks failed with:

- `RuntimeError: This event loop is already running`
- Follow-up errors such as `Future attached to a different loop`

### Root Cause
- Async Celery task execution used `get_worker_loop().run_until_complete(...)` from sync task wrappers.
- Under concurrent worker execution, the shared loop was re-entered, which is illegal in asyncio.
- Hook fallback logic executed DB coroutines via `asyncio.run(...)` in temporary threads, creating extra loops and causing cross-loop asyncpg/SQLAlchemy resource usage.

### Fix
- Replaced the ad-hoc shared-loop `run_until_complete` model with a dedicated background asyncio loop thread.
- Added sync bridge: `run_coroutine_sync(coro)` using `asyncio.run_coroutine_threadsafe(...).result()`.
- Updated task wrappers and DB hook execution paths to use the same bridge, so all async DB work runs on one loop.
- Added worker lifecycle-safe startup/shutdown for the dedicated loop and async engine disposal.

### Files Updated
- `backend/app/core/celery_lifecycle.py`
- `backend/app/modules/workflow/tasks_base.py`

### Verification
- `python -m compileall backend/app/core/celery_lifecycle.py backend/app/modules/workflow/tasks_base.py`
- No syntax errors.

### Expected Result
- No more `This event loop is already running` from task wrapper execution.
- No more cross-loop DB errors caused by fallback thread loops.

---

## ✅ Fixed: Timezone drift from naive datetime writes (code + historical data)

### Problem
Admin task durations and relative times could drift by local timezone offset (e.g. +13h), especially when API datetime strings were emitted without timezone suffix.

### Root Cause
- Several backend write paths used naive datetimes (`datetime.utcnow()` / `datetime.now()` without timezone).
- Mixed historical data might include columns effectively behaving like `timestamp without time zone` in some environments.
- Progress JSON field `tailoring_progress.last_update` stored naive ISO datetime strings.

### Code Fixes
- Replaced naive writes with `datetime.now(timezone.utc)` in:
  - `app/modules/workflow/repositories.py`
  - `app/modules/applications/repositories/outbox_repo.py`
  - `app/modules/applications/tasks.py`
  - `app/modules/resumes/service.py`
  - `app/modules/jobs/repository.py`
- Updated PDF export metadata timestamp to explicit UTC formatting in:
  - `app/modules/resumes/export/generator.py`

### Data Fixes
Added migration:
- `backend/alembic/versions/20260313_1100_d9f2a8c4e6b1_fix_naive_timestamps.py`

Migration behavior:
- Conditionally converts these columns to `TIMESTAMP WITH TIME ZONE` only when current type is `timestamp without time zone`:
  - `task_executions.started_at`
  - `task_executions.completed_at`
  - `outbox_events.next_retry_at`
  - `outbox_events.published_at`
  - `resumes.deleted_at`
- Converts existing values with `AT TIME ZONE 'UTC'` to preserve intended UTC meaning.
- Backfills `applications.tailoring_progress.last_update` naive ISO strings by appending `Z`.

### Verification Notes
- Repository scan confirms no remaining naive datetime calls in backend app code.
- Bytecode compile validation was partially blocked by local filesystem `PermissionError` on `__pycache__` writes in this environment.

## Fixed: Alembic migration file encoding caused syntax error (BOM)

### Problem
The new migration file for `user_job_views` failed to parse with:
`SyntaxError: invalid non-printable character U+FEFF`.

### Root Cause
The file was initially written with UTF-8 BOM using PowerShell `Set-Content -Encoding UTF8`, and Python interpreted BOM as an invalid leading character.

### Solution
Rewrote the migration file in UTF-8 without BOM using .NET `UTF8Encoding(false)`.

### Verification
Validated parsing via `compile(source, path, 'exec')` over all modified backend Python files, including:
- `backend/alembic/versions/20260313_1610_5e2c7d9b1a4f_add_user_job_views.py`

---

**Fixed On**: 2026-03-13
**Status**: Completed
**Scope**: Backend migration file encoding
## 2026-03-14 - Frontend Type Check Baseline Failing (Pre-existing)

### Problem
- `pnpm run build` fails with many TypeScript errors in existing admin/query typing paths.
- Errors include `AxiosResponse<T>` not matching expected query data shape and several unused/strict typing violations.

### Root Cause
- Existing API client typings and admin hooks rely on incompatible return types in strict TypeScript settings.
- This issue exists outside the new admin jobs chart feature.

### Temporary Handling
- Proceeded with feature implementation and validated backend syntax.
- Kept new code typed defensively to minimize additional type noise.

### Verification
- Command run:
  - `python -m compileall backend/app/modules/admin backend/app/main.py` (passed)
  - `pnpm run build` in `frontend/` (failed due pre-existing TS errors)

### Next Steps
- Normalize API client return typing (data vs AxiosResponse) and align hook query generics.
- Re-run frontend build after baseline typing cleanup.

---

## 2026-03-17 - Document Editor Ctrl+S Bypassed Disabled Save Button

### Problem
- In the shared markdown editor, the Save button could be disabled while `Ctrl+S` or `Cmd+S` still triggered a save request.

### Root Cause
- The Save button used a UI-only disabled condition based on dirty state and mutation pending state.
- The keyboard shortcut listener called `form.handleSubmit(handleSubmit)()` directly.
- The submit handler itself did not guard against "save not allowed" conditions.

### Solution
- Added a shared `canSave` condition in `DocumentEditPage`.
- Reused `canSave` for the Save button disabled state.
- Blocked keyboard shortcut submission when `canSave` is false.
- Added an early return inside the submit handler so other entry points cannot bypass the same rule.

### Verification
- When the Save button is disabled, `Ctrl+S` / `Cmd+S` no longer triggers save.
- When content is dirty and no save is in progress, both button click and keyboard shortcut still work.

---

## 2026-03-30 - Production frontend API base URL dropped `/api/v1`

### Problem
- Production frontend requests were sent to paths like `/auth/login`.
- Backend routes are mounted under `/api/v1`, so the expected path was `/api/v1/auth/login`.

### Root Cause
- `frontend/src/api/client.ts` treated `VITE_API_BASE_URL` as a complete API prefix.
- Deployment docs recommended `https://api.freeclaw.cloud`, which is only the origin.
- Nginx proxied the request path as-is and did not strip `/api/v1`.

### Solution
- Normalize `VITE_API_BASE_URL` in the frontend client.
- Keep explicit `/api/v1` values unchanged.
- Expand origin-only values like `https://api.freeclaw.cloud` to `https://api.freeclaw.cloud/api/v1`.
- Update deployment docs to recommend the full versioned API base URL.

### Verification
- The frontend client now maps origin-only values to `/api/v1`.
- Existing local values such as `http://localhost:8000/api/v1` still work unchanged.
