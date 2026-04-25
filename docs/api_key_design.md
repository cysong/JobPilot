# API Key 功能设计

> 状态：设计已确认，进入实施
> 范围：MVP（仅站点拥有者本人使用），但数据模型与认证抽象保留多用户扩展能力

## 1. 目标与范围

让外部脚本 / 自动化平台（n8n、cron、curl 等）通过长期凭证调用 JobPilot 后端的业务接口，无需走 JWT 登录流程。

MVP 阶段：

- 仅本人使用，单用户多 key
- 不做 scope（默认与该用户登录态等价权限）
- 不做限流（沿用现有 middleware）
- 审计仅记 `last_used_at`

但表结构与认证抽象**预留**：scope 数组、过期时间、撤销时间、`auth_method` 标识，后续开放给所有用户时无需迁表。

## 2. 数据模型

新建 `api_keys` 表，归属在新模块 `backend/app/modules/api_keys/`。

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | `String(36)` PK | UUID |
| `user_id` | `int` FK→`users.id` ON DELETE CASCADE | 持有者 |
| `name` | `String(100)` NOT NULL | 用户给 key 起的名字（如 `n8n-integration`）|
| `prefix` | `String(16)` INDEX NOT NULL | 明文前缀（前 12 字符），用于列表展示和快速过滤 |
| `key_hash` | `Text` UNIQUE NOT NULL | SHA-256 of full plaintext key |
| `scopes` | `JSONB` NOT NULL DEFAULT `'[]'` | 预留；空数组 = 全权限 |
| `last_used_at` | `TIMESTAMPTZ` NULL | 最近一次成功验证时间 |
| `expires_at` | `TIMESTAMPTZ` NULL | 预留；NULL = 永不过期 |
| `revoked_at` | `TIMESTAMPTZ` NULL | 软删除/撤销时间 |
| `created_at` | `TIMESTAMPTZ` NOT NULL DEFAULT `now()` | |

索引：

- `ix_api_keys_user_id`
- `ix_api_keys_prefix`
- `uq_api_keys_key_hash`（唯一）

## 3. Key 格式与存储

**明文格式**：`jp_live_<43字符 URL-safe 随机>`（`secrets.token_urlsafe(32)` 产出 43 字符）。

**生成逻辑**：

```python
import secrets, hashlib
plaintext = f"jp_live_{secrets.token_urlsafe(32)}"  # e.g. jp_live_xK9...
prefix = plaintext[:12]                              # "jp_live_xK9a"
key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
```

**存储原则**：

- 数据库**只存 `key_hash` 和 `prefix`**，明文 plaintext 仅在 `POST /api-keys` 响应里返回一次
- 验证时 `SELECT ... WHERE prefix = $prefix AND key_hash = $hash AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())`
- 一次只查一行，不需要全表 hash 比对

## 4. 认证集成（方式 1：全局替换）

改造 `app/core/security.py::get_current_user`，按 token 形态分发：

```python
async def get_current_user(credentials, db):
    token = credentials.credentials
    if token.startswith("jp_live_"):
        user, key = await _resolve_api_key(db, token)
        user._auth_method = "api_key"
        user._api_key_id = key.id
        return user
    user = await _resolve_jwt(db, token)
    user._auth_method = "jwt"
    user._api_key_id = None
    return user
```

并新增一个**严格 dependency** 用于敏感路由：

```python
async def require_jwt_only(credentials, db):
    if credentials.credentials.startswith("jp_live_"):
        raise UnauthorizedError("This endpoint does not accept API keys")
    return await _resolve_jwt(db, credentials.credentials)
```

> 路由层面 99% 不需要改，**只把"必排除清单"上的路由换成 `require_jwt_only`**。

### `User` 对象上的 auth 元信息

通过临时属性 `_auth_method` / `_api_key_id` 携带（不入库），给后续日志、限流、scope 检查用。

## 5. 敏感路由排除清单（必须 `require_jwt_only`）

| 文件 | 路由 | 原因 |
|---|---|---|
| `auth/router.py` | `POST /auth/change-password` | 改密码 |
| `auth/router.py` | `POST /auth/change-email/request` | 改邮箱 = 接管账户 |
| `auth/router.py` | `POST /auth/resend-verification-email` | 防被借用作邮件骚扰 |
| `users/profile_router.py` | `PATCH /users/profile` | 改姓名/头像（身份字段） |
| `api_keys/router.py` | 全部 3 个端点 | 防 key 自我繁殖与撤销绕过 |
| `admin/dependencies.py::require_admin` | 所有挂 admin 链路 | 管理员能力不能用 API key 触发 |

> `forgot-password` / `reset-password` / `verify-email` / `change-email/confirm` / `register` / `login` 不依赖 `Authorization` header（用一次性 token 或纯凭证），天然不会被 API key 滥用，无需处理。
> `GET /auth/me` 可放行（信息无害）。

## 6. 管理端点

`backend/app/modules/api_keys/router.py`：

```
POST   /api/v1/api-keys              require_jwt_only
GET    /api/v1/api-keys              require_jwt_only
DELETE /api/v1/api-keys/{id}         require_jwt_only
```

### `POST /api-keys`

请求：`{ "name": "n8n-integration", "expires_at": null }`

响应（**仅此一次**返回 plaintext）：
```json
{
  "id": "uuid",
  "name": "n8n-integration",
  "prefix": "jp_live_xK9a",
  "plaintext": "jp_live_xK9a...full",
  "scopes": [],
  "expires_at": null,
  "created_at": "..."
}
```

### `GET /api-keys`

返回当前用户所有未撤销的 key（按 `created_at` 倒序），**不含 plaintext**：
```json
[
  { "id": "...", "name": "...", "prefix": "jp_live_xK9a",
    "last_used_at": "...", "expires_at": null,
    "revoked_at": null, "created_at": "..." }
]
```

### `DELETE /api-keys/{id}`

软删除：`UPDATE api_keys SET revoked_at = now() WHERE id = ? AND user_id = ?`。返回 `204`。

## 7. 安全细节与已知坑

1. **`last_used_at` 写放大**：MVP 阶段每次同步写。后续若 QPS 上来，再改成节流写（同一 key 1 分钟内只更新一次）或 Celery 异步写。
2. **错误信息一致性**：key 不存在 / 已撤销 / 已过期 → 全部返回 `401 Invalid credentials`，不分别提示。
3. **日志脱敏**：确认 `app/core/custom_route.py` 与 access log 不落 `Authorization` header（如已脱敏，加单测保护；否则补一层 middleware 屏蔽）。
4. **缓存禁忌**：API key 验证**每次必须查库**，不要在内存里缓存 hash → user 映射，否则用户撤销 key 后无法立即生效。
5. **Swagger UI**：复用 `HTTPBearer`，用户在 "Authorize" 弹窗里粘 plaintext key 即可。文档说明里加一句"Both JWT and API keys accepted"。
6. **CORS / Origin**：API key 调用通常无浏览器 Origin。当前未做 Origin 校验，无需处理；将来若加，记得为 API key 路径放行。
7. **限流维度**：MVP 不做。后续按 `_api_key_id` 维度独立限流（应低于人类用户配额，避免一把 key 把账户额度打爆）。
8. **scope 升级路径**：`scopes` 字段已就位。开放给其他用户时，新增 `require_scope("jobs:read")` dependency，从 `user._api_key_scopes` 校验即可，无需迁表。

## 8. 文件落点

```
backend/app/modules/api_keys/
  __init__.py
  models.py        # ApiKey
  schemas.py       # ApiKeyCreate / ApiKeyResponse / ApiKeyCreatedResponse
  service.py       # generate_api_key / list_api_keys / revoke_api_key / verify_api_key
  router.py        # /api/v1/api-keys
backend/app/core/security.py            # 改造 get_current_user，新增 require_jwt_only
backend/app/api/v1/router.py            # include api_keys router
backend/alembic/versions/<ts>_add_api_keys.py
```

## 9. 实施顺序

1. ✅ 文档（本文件）
2. migration + `ApiKey` model + schemas
3. service（generate / list / revoke / verify）
4. router（管理端点，挂 `require_jwt_only`）
5. 改造 `get_current_user`，新增 `require_jwt_only`
6. 把第 5 节排除清单上的路由换为 `require_jwt_only`
7. 在 `app/api/v1/router.py` 注册 `api_keys.router`
8. `alembic upgrade head` + 冒烟测试（curl 创建 key、列表、撤销；用 key 调 `GET /jobs`、确认 `POST /auth/change-password` 被拒 401）

## 10. 前端（不在本次范围）

待后端打通后单独排期：

- 设置页加 "API Keys" tab
- 创建按钮 → 表单（name 必填）→ 弹窗一次性显示 plaintext + 复制按钮 + 红字"关闭后无法再次查看"
- 列表展示 `prefix`、`name`、`last_used_at`、撤销按钮
