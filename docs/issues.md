# 问题修复记录

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
