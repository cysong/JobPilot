# 用户账户安全功能设计

## 1. 文档目标

本文档用于设计 JobPilot 的用户账户安全相关功能，覆盖：

- 忘记密码
- 通过邮箱重置密码
- 修改密码
- 修改邮箱
- 验证邮箱
- 前后端实现位置
- 所需接口
- 菜单与页面入口

当前系统已具备基础认证能力：

- 用户注册
- 用户登录
- 获取当前用户信息 `GET /api/v1/auth/me`

但账户安全链路尚未完整，尤其缺少邮箱验证、密码找回、账户安全设置等能力。

---

## 2. 设计目标

- 建立完整的邮箱身份确认机制
- 支持用户在忘记密码时通过邮箱自助恢复访问
- 支持已登录用户安全地修改密码
- 支持已登录用户修改邮箱并验证新邮箱归属
- 在前端提供清晰的账户设置与安全设置入口
- 为后续扩展 2FA、登录审计、安全通知预留结构

---

## 3. 功能范围与优先级

### 3.1 P0

- 邮箱验证
- 忘记密码
- 邮箱重置密码
- 已登录用户修改密码
- 设置页中的账户与安全入口

### 3.2 P1

- 已登录用户修改邮箱
- 顶部未验证邮箱提示
- 邮件重发限流
- 安全事件审计日志

### 3.3 暂不纳入本轮

- 双因素认证（2FA）
- 登录历史与设备管理
- 异常登录告警
- OAuth 第三方登录

---

## 4. 当前系统现状

### 4.1 后端现状

现有认证实现位于：

- `backend/app/modules/auth/models.py`
- `backend/app/modules/auth/schemas.py`
- `backend/app/modules/auth/service.py`
- `backend/app/modules/auth/router.py`
- `backend/app/core/security.py`

当前已有接口：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### 4.2 前端现状

现有认证页面与调用层位于：

- `frontend/src/features/auth/Login.tsx`
- `frontend/src/features/auth/Register.tsx`
- `frontend/src/api/auth.ts`
- `frontend/src/store/authStore.ts`

当前菜单入口位于：

- `frontend/src/components/layout/UserNav.tsx`

当前 `Settings` 与 `Profile` 仍是占位页。

---

## 5. 总体设计思路

本次设计建议继续复用现有 `auth` 模块作为账户安全主域，不额外拆出新的重型模块。

职责划分：

- `auth` 模块：
  - 注册、登录
  - 邮箱验证
  - 忘记密码 / 重置密码
  - 修改密码
  - 修改邮箱
- `users` 模块：
  - 继续负责用户资料、技能、偏好等非认证类能力

这样可以保持领域边界清晰，避免把安全相关逻辑拆散到多个模块。

补充边界约定：

- `Profile` 页面负责用户求职偏好配置
- `Settings` 页面负责账户与安全设置
- `users.preferences` 仅存放求职偏好，不存放邮箱验证状态、密码状态、一次性 token 等安全事实
- 账户安全相关事实字段继续保留在 `users` 表显式字段中，由 `auth` 域负责读写

### 5.1 Profile 与 Settings 的页面职责

- `Profile`
  - 默认定制深度 `default_tailoring_level`
  - 求职目的地（新西兰城市，多选）
  - 期望年薪（单值或区间）
- `Settings / Account`
  - 当前邮箱
  - 邮箱验证状态
  - 重发验证邮件
  - 修改邮箱
- `Settings / Security`
  - 修改密码
  - 最近修改密码时间
  - 后续 2FA / 登录历史 / 安全日志预留

这样拆分后：

- 求职偏好进入 `Profile`
- 凭证与账号治理进入 `Settings`
- 前端信息架构更稳定，后续实现不会把 Profile 和 Security 混在一起

---

## 6. 数据模型设计

### 6.1 users 表扩展

建议在 `users` 表中新增以下字段：

- `email_verified_at TIMESTAMPTZ NULL`
- `password_changed_at TIMESTAMPTZ NULL`
- `preferences JSONB NOT NULL DEFAULT '{}'::jsonb`

字段含义：

- `email_verified_at`
  - 不为空表示当前邮箱已验证
- `password_changed_at`
  - 记录最近一次成功修改密码的时间
  - 用于安全设置页展示
  - 后续可用于安全审计
- `preferences`
  - 存储用户求职偏好
  - 当前仅保留 3 组字段，不继续扩展其他简历偏好或 Cover Letter 风格字段

`preferences` 建议结构：

```json
{
  "default_tailoring_level": "light",
  "job_locations": [
    "Auckland",
    "Wellington"
  ],
  "salary_expectation": {
    "mode": "range",
    "currency": "NZD",
    "period": "yearly",
    "min": 120000,
    "max": 150000,
    "value": null
  }
}
```

字段约束建议：

- `default_tailoring_level`
  - 可选值：`light` / `deep`
  - 用于创建申请时的默认定制深度
- `job_locations`
  - 数组，允许多选
  - 当前范围限定为新西兰城市
  - 建议第一版前后端共用一份受控枚举，不接受自由输入
- `salary_expectation`
  - 表示期望年薪
  - `currency` 第一版固定为 `NZD`
  - `period` 第一版固定为 `yearly`
  - `mode` 支持：
    - `exact`：单个数字年薪
    - `range`：年薪区间
  - 当 `mode=exact` 时使用 `value`
  - 当 `mode=range` 时使用 `min` 与 `max`

新西兰城市建议第一版采用受控选项，例如：

- `Auckland`
- `Wellington`
- `Christchurch`
- `Hamilton`
- `Tauranga`
- `Dunedin`
- `Palmerston North`
- `Queenstown`
- `Napier-Hastings`
- `Nelson`

设计说明：

- 这里只存“用户偏好”，不存系统推导结果
- 这里只表达“求职目的地偏好”，不替代职位筛选参数
- 这里只表达“期望年薪”，不处理时薪、月薪、多币种换算
- 如果后续扩展澳洲或其他市场，再单独扩展国家与币种模型

### 6.2 新增 user_security_tokens 表

建议新增独立表统一管理一次性安全令牌，而不是把临时 token 状态直接放在 `users` 表。

建议表结构：

```sql
CREATE TABLE user_security_tokens (
  id TEXT PRIMARY KEY,          -- UUID，Python 端用 uuid.uuid4() 生成
  user_id INTEGER NOT NULL,
  token_hash TEXT NOT NULL,
  token_type TEXT NOT NULL,
  target_email TEXT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_user_security_tokens_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_security_tokens_user_type
  ON user_security_tokens (user_id, token_type);

CREATE INDEX idx_user_security_tokens_expires_at
  ON user_security_tokens (expires_at);
```

`token_type` 建议支持以下值：

- `EMAIL_VERIFY`
- `PASSWORD_RESET`
- `EMAIL_CHANGE`

各类型 token 有效期：

| token_type | 有效期 | 原因 |
|---|---|---|
| `EMAIL_VERIFY` | 24 小时 | 用户有足够时间处理 |
| `PASSWORD_RESET` | 1 小时 | 安全敏感，尽量缩短窗口期 |
| `EMAIL_CHANGE` | 24 小时 | 用户有足够时间在新邮箱确认 |

字段说明：

- `token_hash`
  - 数据库存哈希值，不存明文 token
- `target_email`
  - 用于修改邮箱流程，保存待确认的新邮箱
- `consumed_at`
  - 表示该 token 是否已被消费

旧 token 失效策略：

- 每次生成新 token 前，将同 `(user_id, token_type)` 下所有未消费、未过期的旧 token 标记为 `consumed_at = now()`
- 确保同一类型同一时间只有一个有效 token

---

## 7. 核心流程设计

### 7.1 注册后邮箱验证

流程：

1. 用户注册成功
2. 系统创建 `EMAIL_VERIFY` 类型 token
3. 系统发送验证邮件到当前邮箱
4. 用户点击验证链接
5. 后端校验 token
6. 写入 `users.email_verified_at`
7. token 标记消费

设计决策：

- 第一版允许未验证邮箱先登录
- 但前端持续提示未验证状态
- 后续如需增强安全，可把部分敏感操作切到“仅已验证邮箱可用”

### 7.2 忘记密码 / 重置密码

流程：

1. 用户在登录页点击 `Forgot password`
2. 输入邮箱地址
3. 后端若找到用户则生成 `PASSWORD_RESET` token 并发信
4. 不论邮箱是否存在，接口都返回统一成功消息
5. 用户点击邮件中的重置链接
6. 打开重置密码页面并提交新密码
7. 后端校验 token，更新密码，写入 `password_changed_at`
8. token 标记消费

设计决策：

- 接口响应必须统一，避免邮箱枚举
- token 必须有时效且单次消费
- 重置成功后建议要求用户重新登录

### 7.3 已登录修改密码

流程：

1. 用户进入 `Security Settings`
2. 输入当前密码和新密码
3. 后端验证当前密码
4. 更新密码哈希
5. 更新 `password_changed_at`
6. 视策略决定是否让当前登录态失效

设计决策：

- 必须校验当前密码
- 第一版可不做全端登录态强制失效
- 至少要求前端刷新当前用户状态，必要时重新登录

### 7.4 已登录修改邮箱

流程：

1. 用户进入 `Account Settings`
2. 输入新邮箱和当前密码
3. 后端校验当前密码
4. 检查新邮箱未被占用
5. 创建 `EMAIL_CHANGE` token，并将 `target_email` 设为新邮箱
6. 发送确认邮件到新邮箱
7. 用户点击确认链接
8. 后端校验 token
9. 更新 `users.email = target_email`
10. 清空旧邮箱验证状态或直接将新邮箱视为已验证

设计建议：

- 因为用户是通过新邮箱收到确认邮件的，所以确认成功后可直接把新邮箱视为已验证
- 修改邮箱成功后，前端应重新拉取 `me`

---

## 8. 接口设计

### 8.1 公开接口

以下接口均无需登录态，通过 token 本身验证身份：

#### `POST /api/v1/auth/forgot-password`

请求：

```json
{
  "email": "user@example.com"
}
```

响应：

```json
{
  "message": "If an account exists, we have sent password reset instructions."
}
```

说明：

- 即使邮箱不存在，也返回相同文案

#### `POST /api/v1/auth/reset-password`

请求：

```json
{
  "token": "plain-token",
  "new_password": "NewPassword123"
}
```

说明：

- 校验 token 是否存在、未消费、未过期、类型为 `PASSWORD_RESET`

#### `POST /api/v1/auth/verify-email`

请求：

```json
{
  "token": "plain-token"
}
```

说明：

- 校验 token 后设置 `email_verified_at`

#### `POST /api/v1/auth/change-email/confirm`

请求：

```json
{
  "token": "plain-token"
}
```

说明：

- 公开接口，token 本身已绑定 `user_id` 和 `target_email`，无需登录态
- 校验通过后更新 `users.email = target_email`，并将新邮箱视为已验证
- 前端确认成功后重新拉取 `auth/me`

### 8.2 登录态接口

#### `POST /api/v1/auth/resend-verification-email`

请求：

- 无入参，直接基于当前登录用户处理

说明：

- 若当前邮箱已验证，可直接返回成功并提示无需重复发送
- 限流策略：检查 `user_security_tokens` 中该用户过去 10 分钟内已生成的同类型 token 数量，超过 3 次则拒绝，无需引入 Redis

#### `POST /api/v1/auth/change-password`

请求：

```json
{
  "current_password": "OldPassword123",
  "new_password": "NewPassword123"
}
```

#### `POST /api/v1/auth/change-email/request`

请求：

```json
{
  "new_email": "new@example.com",
  "current_password": "CurrentPassword123"
}
```

说明：

- 校验当前密码
- 新邮箱必须唯一
- 发送确认邮件到新邮箱

#### `GET /api/v1/auth/me`

建议扩展返回，便于前端初始化时一次拿到账户安全状态与 Profile 偏好，不再单独提供 `/auth/security` 端点：

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "User Name",
  "role": "USER",
  "is_active": true,
  "email_verified_at": "2026-03-30T12:00:00Z",
  "password_changed_at": "2026-03-25T09:10:00Z",
  "preferences": {
    "default_tailoring_level": "light",
    "job_locations": ["Auckland", "Wellington"],
    "salary_expectation": {
      "mode": "range",
      "currency": "NZD",
      "period": "yearly",
      "min": 120000,
      "max": 150000,
      "value": null
    }
  }
}
```

说明：

- 安全状态通过 `auth/me` 一次性暴露，不单独提供 `/auth/security` 端点，避免前端初始化时多发请求
- `preferences` 作为用户资料的一部分挂在 `me` 中返回，便于 `Profile` 页与申请创建流程直接消费
- 新用户 `preferences` 为空对象 `{}`，前端消费时需对各字段做空值防护，建议定义明确的默认回退值：
  - `default_tailoring_level` → `"light"`
  - `job_locations` → `[]`
  - `salary_expectation` → `null`
- 若后续需要，也可补充独立的 `users/profile` 读写接口来管理偏好编辑

---

## 9. 后端实现位置

### 9.1 保持在 auth 模块中的内容

建议放在以下文件：

- `backend/app/modules/auth/router.py`
  - 增加账户安全相关接口
- `backend/app/modules/auth/schemas.py`
  - 增加 forgot/reset/verify/change-password/change-email 请求响应模型
- `backend/app/modules/auth/service.py`
  - 增加账户安全业务逻辑
- `backend/app/modules/auth/models.py`
  - 补充 `User` 字段
  - 或新增 `UserSecurityToken` 模型

### 9.2 建议新增的服务文件

建议新增：

- `backend/app/modules/auth/token_service.py`
  - 生成 token
  - hash token
  - 查找 token
  - 校验过期
  - 标记消费

- `backend/app/modules/auth/email_service.py`
  - 发送验证邮件
  - 发送密码重置邮件
  - 发送修改邮箱确认邮件

这样可以避免把所有逻辑堆进 `service.py`。

### 9.3 数据库迁移

需要新增 Alembic migration，命名规范与现有迁移保持一致：`YYYYMMDD_HHMM_<hash>_<description>.py`

1. 给 `users` 表增加：
   - `email_verified_at`
   - `password_changed_at`
   - `preferences`
2. 新建 `user_security_tokens` 表
3. 建索引

---

## 10. 前端实现位置

### 10.1 页面建议

建议新增页面：

- `frontend/src/features/auth/ForgotPassword.tsx`
- `frontend/src/features/auth/ResetPassword.tsx`
- `frontend/src/features/auth/VerifyEmail.tsx`
- `frontend/src/features/auth/ChangeEmailConfirmPage.tsx`
- `frontend/src/features/profile/ProfilePage.tsx`
- `frontend/src/features/settings/AccountSettingsPage.tsx`
- `frontend/src/features/settings/SecuritySettingsPage.tsx`

### 10.2 路由建议

在 `frontend/src/App.tsx` 中新增公开路由：

- `/forgot-password`
- `/reset-password`
- `/verify-email`
- `/change-email-confirm`

新增登录态路由（替换现有占位页）：

- `/profile`
- `/settings/account`
- `/settings/security`

并将现有 `/settings` 从占位页改成：

- 重定向到 `/settings/account`
- 或渲染带 tab 的设置页容器

### 10.3 API 调用层

建议继续扩展现有：

- `frontend/src/api/auth.ts`
- `frontend/src/api/users.ts` 或在现有 `users` 相关 API 中补充 profile 能力

建议新增方法：

- `forgotPassword`（公开）
- `resetPassword`（公开）
- `verifyEmail`（公开）
- `confirmEmailChange`（公开，对应 `/change-email/confirm`）
- `resendVerificationEmail`（登录态）
- `changePassword`（登录态）
- `requestEmailChange`（登录态）
- `updateProfilePreferences`（登录态）
- `getProfilePreferences`（如果不完全依赖 `auth/me`，登录态）

不再需要单独的 `getSecurityInfo`，安全信息直接从 `auth/me` 的返回中消费。

### 10.4 状态管理

基于现有 `authStore`，建议：

- 登录后继续使用 `getCurrentUser()` 拉当前用户
- 增加对 `email_verified_at` 的消费
- 增加对 `password_changed_at` 的消费
- 增加对 `preferences.default_tailoring_level` 的消费
- 增加对 `preferences.job_locations` 的消费
- 增加对 `preferences.salary_expectation` 的消费
- 修改邮箱成功后重新执行一次 `getCurrentUser()`
- 修改 Profile 偏好成功后同步刷新本地当前用户信息

---

## 11. 菜单与页面入口设计

### 11.1 用户菜单

当前菜单已有：

- `Profile`
- `Settings`

建议：

- `Profile` 进入真实的用户偏好页，而不是占位页
- 保留 `Settings`
- 点击后进入真正的设置页，而不是占位页

### 11.2 Profile 页

展示与操作：

- 默认定制深度
- 求职目的地（新西兰城市多选）
- 期望年薪

交互建议：

- 求职目的地使用多选下拉或多选弹层
- 期望年薪支持两种输入模式：
  - `Exact yearly salary`
  - `Yearly salary range`
- 所有 Profile 偏好均为用户可编辑配置，不应出现在 Security 页中

### 11.3 设置页结构

建议拆成两个一级 tab：

- `Account`
- `Security`

#### Account 页

展示与操作：

- 当前邮箱
- 邮箱验证状态
- `Resend verification email`
- `Change email`

#### Security 页

展示与操作：

- 修改密码表单
- 最近修改密码时间
- 后续可扩展 2FA、登录历史

### 11.4 登录页入口

建议在登录页密码输入框附近新增：

- `Forgot password?`

### 11.5 顶部验证提示

对于未验证邮箱用户，建议在主应用中增加顶部横幅：

- 提示邮箱尚未验证
- 提供 `Resend email` 操作
- 提供跳转到账户设置页的入口

---

## 12. 邮件设计

### 12.1 邮件服务

使用 **Resend** 作为邮件发送服务。

依赖与配置：

- 后端新增依赖：`resend`（Python SDK）
- `.env` 中新增配置项：
  - `RESEND_API_KEY=re_xxxxx`
  - `RESEND_FROM_EMAIL=noreply@freeclaw.cloud`
  - `APP_FRONTEND_URL=https://app.freeclaw.cloud`（用于邮件中的跳转链接拼接）
- `email_service.py` 通过 `resend.Emails.send()` 发送邮件

### 12.2 邮件类型

至少需要三种邮件模板：

- 邮箱验证邮件
- 重置密码邮件
- 修改邮箱确认邮件

### 12.3 邮件内容要求

每封邮件建议包含：

- 操作说明
- 过期时间提示
- 若非本人操作可忽略的提示
- 按钮链接
- 纯文本备用链接

邮件正文使用 HTML 字符串内联实现，第一版不引入额外模板引擎。

### 12.4 链接格式建议

前端页面建议承接邮件链接：

- `https://app.freeclaw.cloud/verify-email?token=...`
- `https://app.freeclaw.cloud/reset-password?token=...`
- `https://app.freeclaw.cloud/change-email-confirm?token=...`

---

## 13. 安全要求

- token 必须设置过期时间（各类型有效期见 6.2）
- token 必须单次消费
- 生成新 token 前必须将同类型旧 token 标记为已消费
- 数据库存储 token 哈希，不存明文
- 忘记密码接口必须统一响应，避免用户枚举
- 限流策略：基于数据库实现，无需引入 Redis
  - 检查过去 10 分钟内同 `(user_id, token_type)` 的 token 生成数量
  - 超过 3 次则返回 429，提示稍后再试
- 修改密码和修改邮箱都必须校验当前密码
- 新密码继续沿用现有复杂度校验规则

---

## 14. 实施建议顺序

### 阶段 1

- 扩展 `users` 表
- 新增 `user_security_tokens`
- 实现忘记密码和重置密码

### 阶段 2

- 实现邮箱验证
- 实现重发验证邮件
- 注册后自动发验证邮件

### 阶段 3

- 实现修改密码
- 接入安全设置页

### 阶段 4

- 实现修改邮箱
- 接入账户设置页
- 增加顶部未验证邮箱提示

---

## 15. 受影响文件清单

### 后端

- `backend/app/modules/auth/models.py`
- `backend/app/modules/auth/schemas.py`
- `backend/app/modules/auth/service.py`
- `backend/app/modules/auth/router.py`
- `backend/app/core/security.py`
- `backend/alembic/versions/*`

### 前端

- `frontend/src/App.tsx`
- `frontend/src/api/auth.ts`
- `frontend/src/api/users.ts`
- `frontend/src/types/auth.ts`
- `frontend/src/store/authStore.ts`
- `frontend/src/features/auth/*`
- `frontend/src/features/profile/*`
- `frontend/src/features/settings/*`
- `frontend/src/components/layout/UserNav.tsx`

---

## 16. 开发注意事项

- 后端接口命名应保持与现有 `/auth/*` 风格一致
- 不要把一次性安全状态塞进 `users` 表中过多临时字段
- `users.preferences` 当前只保留：
  - `default_tailoring_level`
  - `job_locations`
  - `salary_expectation`
- 前端消费 `preferences` 时必须对各字段做空值防护，新用户 `preferences` 为 `{}`
- 前端提示文案统一使用英文，符合现有 UI 文案规范
- `user_security_tokens.id` 使用 UUID，Python 端通过 `uuid.uuid4()` 生成
- 邮件发送使用 Resend Python SDK，`RESEND_API_KEY`、`RESEND_FROM_EMAIL`、`APP_FRONTEND_URL` 必须在 `.env` 中配置
- 如果后续要改动需求文档或架构文档，应单独出更新计划

---

## 17. 结论

本设计建议以现有 `auth` 模块为中心补齐账户安全闭环，优先完成：

- 邮箱验证
- 忘记密码 / 重置密码
- 修改密码
- 设置页入口

在此基础上再扩展修改邮箱与更完整的安全治理能力。这样改动范围可控，符合当前项目结构，也能明显提升账户体系完整性。
