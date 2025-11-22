# JobPilot v0.1 全栈执行计划

## 总体策略

采用**前后端联调**的渐进式开发模式，每个阶段都交付可演示的完整功能。通过前端页面直观验证系统功能，确保每一步都能独立运行和测试。

### 开发原则

1. **端到端优先**: 每个阶段都是完整的功能闭环（后端 API + 前端页面）
2. **立即可见**: 通过浏览器直观验证功能是否正常
3. **渐进增强**: 先建立骨架，再丰富细节
4. **独立可测**: 每个阶段完成后都能独立演示

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         Development Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Stage 0: 项目初始化                                             │
│  ├─ 后端项目结构                                                 │
│  ├─ 前端项目结构                                                 │
│  ├─ 数据库配置                                                   │
│  └─ 开发环境验证                                                 │
│                                                                 │
│  Stage 1: 认证系统 (Auth) 🔐                                    │
│  ├─ 后端: JWT 认证 API                                          │
│  ├─ 前端: 登录/注册页面                                          │
│  └─ 验证: 成功登录并获取 Token                                   │
│                                                                 │
│  Stage 2: Job 浏览模块 📋                                       │
│  ├─ 后端: Job 列表/详情 API                                     │
│  ├─ 前端: Job 列表页 + 详情页                                   │
│  └─ 验证: 浏览 Job 并查看详情                                   │
│                                                                 │
│  Stage 3: 简历管理模块 📝                                       │
│  ├─ 后端: Resume CRUD API + Document 版本管理                   │
│  ├─ 前端: 简历列表页 + 编辑器                                   │
│  └─ 验证: 创建/编辑简历并标记为正式版本                          │
│                                                                 │
│  Stage 4: AI Agent 基础 🤖                                      │
│  ├─ 后端: OpenAI 集成 + Prompt 模板                             │
│  ├─ 前端: AI 生成测试页面（可选）                                │
│  └─ 验证: 调用 AI 生成定制简历/求职信                            │
│                                                                 │
│  Stage 5: 申请创建与工作流 ⚙️                                   │
│  ├─ 后端: Application API + Celery 工作流                       │
│  ├─ 前端: 申请创建流程 + 状态展示                                │
│  └─ 验证: 创建申请并自动生成材料                                 │
│                                                                 │
│  Stage 6: 申请管理与材料查看 📊                                 │
│  ├─ 后端: 申请列表/详情 API + PDF 生成                          │
│  ├─ 前端: 申请列表页 + 材料查看/下载                             │
│  └─ 验证: 查看定制简历和求职信，下载 PDF                         │
│                                                                 │
│  Stage 7: 系统集成与优化 🚀                                     │
│  ├─ 错误处理优化                                                │
│  ├─ 加载状态优化                                                │
│  ├─ 数据验证增强                                                │
│  └─ 验证: 完整的端到端流程测试                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 0: 项目初始化 (Foundation Setup)

### 目标
建立前后端项目骨架，配置开发环境，确保基础设施就绪。

### 后端任务 (Backend)

#### 0.1 项目结构初始化

```bash
backend/
├── .env.example                    # 环境变量模板
├── .gitignore
├── pyproject.toml                  # Poetry 依赖配置
├── alembic.ini                     # Alembic 配置
├── README.md
├── alembic/
│   ├── env.py                      # Alembic 环境配置
│   └── versions/                   # 迁移版本目录
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 应用入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Settings (Pydantic BaseSettings)
│   │   ├── database.py             # async_sessionmaker + get_db
│   │   ├── security.py             # JWT/密码工具（预留）
│   │   └── exceptions.py           # 自定义异常类
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── base_model.py           # SQLAlchemy Base
│   │   ├── enums.py                # 全局枚举
│   │   └── pagination.py           # 分页工具
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # 全局依赖注入
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py           # 聚合所有模块路由
│   └── modules/                    # 业务模块（后续阶段添加）
└── scripts/
    └── init_db.py                  # 数据库初始化脚本
```

#### 0.2 核心配置文件

**pyproject.toml** (Poetry 依赖):
```toml
[tool.poetry]
name = "jobpilot-backend"
version = "0.1.0"
description = "JobPilot Backend API"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
sqlalchemy = "^2.0.25"
asyncpg = "^0.29.0"
alembic = "^1.13.1"
pydantic = {extras = ["email"], version = "^2.5.3"}
pydantic-settings = "^2.1.0"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-multipart = "^0.0.6"
celery = {extras = ["redis"], version = "^5.3.6"}
redis = "^5.0.1"
openai = "^1.10.0"
jspdf = "^2.5.1"
markdown = "^3.5.2"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.4"
pytest-asyncio = "^0.23.3"
httpx = "^0.26.0"
black = "^24.1.1"
ruff = "^0.1.14"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

**.env.example**:
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobpilot

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI (via spec-kit Gateway)
OPENAI_API_KEY=sk-xxxxx
OPENAI_API_BASE=https://api.openai.com/v1

# CORS
CORS_ORIGINS=["http://localhost:5173"]

# Environment
ENVIRONMENT=development
```

**app/core/config.py**:
```python
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_API_BASE: str = "https://api.openai.com/v1"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # Environment
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

**app/core/database.py**:
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """Dependency for getting async database sessions"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
```

**app/shared/base_model.py**:
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime
from datetime import datetime

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
```

**app/main.py** (最小启动文件):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="JobPilot API",
    version="0.1.0",
    description="AI-powered job application assistant"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

#### 0.3 数据库初始化

```bash
# 安装依赖
cd backend
poetry install

# 创建数据库
createdb jobpilot

# 初始化 Alembic
poetry run alembic init alembic

# 配置 alembic/env.py 使用 async 引擎

# 创建初始迁移（先创建基础模型后执行）
poetry run alembic revision --autogenerate -m "Initial schema"
poetry run alembic upgrade head
```

### 前端任务 (Frontend)

#### 0.4 项目结构初始化

```bash
# 使用 Vite 创建项目
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install

# 安装核心依赖
npm install react-router-dom@6 zustand axios @tanstack/react-query
npm install -D tailwindcss postcss autoprefixer
npm install lucide-react class-variance-authority clsx tailwind-merge

# 初始化 Tailwind CSS
npx tailwindcss init -p
```

**项目结构**:
```bash
frontend/
├── public/
├── src/
│   ├── api/                        # API 调用封装
│   │   ├── client.ts               # Axios 客户端配置
│   │   └── auth.ts                 # 认证 API（Stage 1）
│   ├── components/                 # 通用组件
│   │   └── ui/                     # shadcn/ui 组件
│   ├── features/                   # 功能模块（按 Stage 添加）
│   ├── hooks/                      # 自定义 Hooks
│   ├── store/                      # Zustand 状态管理
│   │   └── authStore.ts            # 认证状态
│   ├── types/                      # TypeScript 类型
│   ├── utils/                      # 工具函数
│   ├── App.tsx
│   ├── main.tsx
│   └── router.tsx                  # 路由配置
├── .env.example
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

#### 0.5 核心配置文件

**vite.config.ts**:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**tailwind.config.js**:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**.env.example**:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

**src/api/client.ts**:
```typescript
import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for adding auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for handling errors
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

export default apiClient
```

**src/App.tsx** (最小启动文件):
```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 py-6">
            <h1 className="text-3xl font-bold text-gray-900">JobPilot</h1>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 py-6">
          <p className="text-gray-600">Frontend is ready! 🚀</p>
        </main>
      </div>
    </QueryClientProvider>
  )
}

export default App
```

### 验收标准 ✅

- [ ] 后端项目结构创建完成
- [ ] 前端项目结构创建完成
- [ ] 后端启动成功：`http://localhost:8000/health` 返回健康状态
- [ ] 前端启动成功：`http://localhost:5173` 显示首页
- [ ] 数据库连接成功
- [ ] Redis 连接成功
- [ ] 环境变量加载正确

### 预估时间: 2-3 小时

---

## Stage 1: 认证系统 (Authentication) 🔐

### 目标
实现完整的用户注册/登录功能，前端可以通过表单注册、登录并获取 JWT Token。

### 后端任务 (Backend)

#### 1.1 数据模型

**app/shared/enums.py**:
```python
from enum import Enum

class Role(str, Enum):
    USER = "USER"
    VIP = "VIP"
    ADMIN = "ADMIN"
```

**app/modules/auth/models.py**:
```python
from sqlalchemy import String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.base_model import Base, TimestampMixin
from app.shared.enums import Role

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[Role] = mapped_column(
        SQLEnum(Role, native_enum=False),
        default=Role.USER,
        nullable=False
    )
```

#### 1.2 Schemas (Pydantic)

**app/modules/auth/schemas.py**:
```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    email: str
    role: str

    class Config:
        from_attributes = True
```

#### 1.3 安全工具

**app/core/security.py**:
```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict | None:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
```

#### 1.4 依赖注入

**app/modules/auth/dependencies.py**:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.auth.models import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user
```

#### 1.5 Service 层

**app/modules/auth/service.py**:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from uuid import uuid4

from app.modules.auth.models import User
from app.modules.auth.schemas import UserCreate, UserLogin, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token

class AuthService:
    @staticmethod
    async def register(db: AsyncSession, user_data: UserCreate) -> TokenResponse:
        """Register a new user"""
        # Check if email already exists
        result = await db.execute(select(User).where(User.email == user_data.email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create new user
        new_user = User(
            id=str(uuid4()),
            email=user_data.email,
            password_hash=hash_password(user_data.password)
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # Create access token
        access_token = create_access_token({"sub": new_user.id})
        return TokenResponse(access_token=access_token)

    @staticmethod
    async def login(db: AsyncSession, login_data: UserLogin) -> TokenResponse:
        """Login existing user"""
        result = await db.execute(select(User).where(User.email == login_data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )

        # Create access token
        access_token = create_access_token({"sub": user.id})
        return TokenResponse(access_token=access_token)
```

#### 1.6 Router

**app/modules/auth/router.py**:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.schemas import UserCreate, UserLogin, TokenResponse, UserResponse
from app.modules.auth.service import AuthService
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    return await AuthService.register(db, user_data)

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login existing user"""
    return await AuthService.login(db, login_data)

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user
```

#### 1.7 集成到主应用

**app/api/v1/router.py**:
```python
from fastapi import APIRouter
from app.modules.auth.router import router as auth_router

api_router = APIRouter()

api_router.include_router(auth_router)
```

**app/main.py** (更新):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title="JobPilot API",
    version="0.1.0",
    description="AI-powered job application assistant"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
```

### 前端任务 (Frontend)

#### 1.8 认证 API 封装

**src/api/auth.ts**:
```typescript
import apiClient from './client'

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface UserResponse {
  id: string
  email: string
  role: string
}

export const authApi = {
  register: (data: RegisterRequest) =>
    apiClient.post<TokenResponse>('/auth/register', data),

  login: (data: LoginRequest) =>
    apiClient.post<TokenResponse>('/auth/login', data),

  getCurrentUser: () =>
    apiClient.get<UserResponse>('/auth/me'),
}
```

#### 1.9 认证状态管理

**src/store/authStore.ts**:
```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  role: string
}

interface AuthState {
  user: User | null
  token: string | null
  setAuth: (user: User, token: string) => void
  clearAuth: () => void
  isAuthenticated: boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      setAuth: (user, token) => {
        localStorage.setItem('access_token', token)
        set({ user, token, isAuthenticated: true })
      },

      clearAuth: () => {
        localStorage.removeItem('access_token')
        set({ user: null, token: null, isAuthenticated: false })
      },
    }),
    {
      name: 'auth-storage',
    }
  )
)
```

#### 1.10 登录/注册页面

**src/features/auth/LoginPage.tsx**:
```typescript
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const navigate = useNavigate()
  const setAuth = useAuthStore((state) => state.setAuth)

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: async (response) => {
      const token = response.data.access_token

      // Fetch user info
      const userResponse = await authApi.getCurrentUser()
      setAuth(userResponse.data, token)

      navigate('/jobs')
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Login failed')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    loginMutation.mutate({ email, password })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h2 className="text-3xl font-bold text-center">Sign in to JobPilot</h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loginMutation.isPending}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {loginMutation.isPending ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="text-center">
          <a href="/register" className="text-sm text-blue-600 hover:text-blue-500">
            Don't have an account? Sign up
          </a>
        </div>
      </div>
    </div>
  )
}
```

**src/features/auth/RegisterPage.tsx** (类似结构，调用 `authApi.register`)

#### 1.11 路由配置

**src/router.tsx**:
```typescript
import { createBrowserRouter, Navigate } from 'react-router-dom'
import LoginPage from '@/features/auth/LoginPage'
import RegisterPage from '@/features/auth/RegisterPage'
import { useAuthStore } from '@/store/authStore'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },
  {
    path: '/jobs',
    element: (
      <ProtectedRoute>
        <div>Jobs Page (Coming in Stage 2)</div>
      </ProtectedRoute>
    ),
  },
  {
    path: '/',
    element: <Navigate to="/login" replace />,
  },
])
```

**src/main.tsx** (更新):
```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { router } from './router'
import './index.css'

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
)
```

### 联调测试 🧪

#### 测试流程:
1. 启动后端: `cd backend && poetry run uvicorn app.main:app --reload`
2. 启动前端: `cd frontend && npm run dev`
3. 访问 `http://localhost:5173/register`
4. 注册新用户
5. 登录成功后跳转到 `/jobs`

### 验收标准 ✅

- [ ] 用户可以通过前端注册账号
- [ ] 注册成功后自动登录并跳转
- [ ] 用户可以登录已存在的账号
- [ ] 登录成功后获取 JWT Token
- [ ] Token 保存在 localStorage
- [ ] 访问受保护路由时自动验证 Token
- [ ] 后端 `/api/v1/auth/me` 返回当前用户信息
- [ ] 前端显示用户邮箱和角色

### 预估时间: 4-5 小时

---

## Stage 2: Job 浏览模块 📋

### 目标
用户登录后可以浏览 Job 列表，查看 Job 详情。

### 后端任务 (Backend)

#### 2.1 数据模型

**app/modules/jobs/models.py**:
```python
from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.shared.base_model import Base

class Job(Base):
    __tablename__ = "seek_jobs"

    # Primary fields
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)

    # Status fields
    status: Mapped[str | None] = mapped_column(String(50))
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False)
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Location
    location_label: Mapped[str | None] = mapped_column(String(200))
    location_city: Mapped[str | None] = mapped_column(String(100))

    # Company
    advertiser_name: Mapped[str | None] = mapped_column(String(300))
    company_name: Mapped[str | None] = mapped_column(String(300))

    # Classification
    classification: Mapped[str | None] = mapped_column(String(200))
    sub_classification: Mapped[str | None] = mapped_column(String(200))

    # Salary
    salary_label: Mapped[str | None] = mapped_column(String(200))

    # Work type
    work_types_label: Mapped[str | None] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 2.2 Schemas

**app/modules/jobs/schemas.py**:
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class JobListItem(BaseModel):
    """Job list item response"""
    id: int
    title: str
    abstract: Optional[str]
    location_label: Optional[str]
    company_name: Optional[str]
    salary_label: Optional[str]
    work_types_label: Optional[str]
    listed_at: Optional[datetime]

    class Config:
        from_attributes = True

class JobDetail(BaseModel):
    """Job detail response"""
    id: int
    source_id: str
    title: str
    abstract: Optional[str]
    content: Optional[str]
    location_label: Optional[str]
    location_city: Optional[str]
    company_name: Optional[str]
    advertiser_name: Optional[str]
    classification: Optional[str]
    sub_classification: Optional[str]
    salary_label: Optional[str]
    work_types_label: Optional[str]
    listed_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_expired: bool

    class Config:
        from_attributes = True

class JobListResponse(BaseModel):
    """Paginated job list response"""
    items: List[JobListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
```

#### 2.3 Service 层

**app/modules/jobs/service.py**:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.modules.jobs.models import Job
from app.modules.jobs.schemas import JobListResponse, JobListItem, JobDetail
from math import ceil

class JobService:
    @staticmethod
    async def get_job_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20
    ) -> JobListResponse:
        """Get paginated job list"""
        # Count total jobs
        count_stmt = select(func.count()).select_from(Job).where(Job.is_expired == False)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # Get jobs
        offset = (page - 1) * page_size
        stmt = (
            select(Job)
            .where(Job.is_expired == False)
            .order_by(desc(Job.listed_at))
            .limit(page_size)
            .offset(offset)
        )
        result = await db.execute(stmt)
        jobs = result.scalars().all()

        return JobListResponse(
            items=[JobListItem.model_validate(job) for job in jobs],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size)
        )

    @staticmethod
    async def get_job_detail(db: AsyncSession, job_id: int) -> JobDetail | None:
        """Get job detail by ID"""
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if job:
            return JobDetail.model_validate(job)
        return None
```

#### 2.4 Router

**app/modules/jobs/router.py**:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.jobs.schemas import JobListResponse, JobDetail
from app.modules.jobs.service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("", response_model=JobListResponse)
async def get_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paginated job list (requires authentication)"""
    return await JobService.get_job_list(db, page, page_size)

@router.get("/{job_id}", response_model=JobDetail)
async def get_job_detail(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get job detail by ID"""
    job = await JobService.get_job_detail(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
```

**app/api/v1/router.py** (更新):
```python
from fastapi import APIRouter
from app.modules.auth.router import router as auth_router
from app.modules.jobs.router import router as jobs_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(jobs_router)
```

### 前端任务 (Frontend)

#### 2.5 Job API 封装

**src/api/jobs.ts**:
```typescript
import apiClient from './client'

export interface JobListItem {
  id: number
  title: string
  abstract?: string
  location_label?: string
  company_name?: string
  salary_label?: string
  work_types_label?: string
  listed_at?: string
}

export interface JobDetail extends JobListItem {
  source_id: string
  content?: string
  location_city?: string
  advertiser_name?: string
  classification?: string
  sub_classification?: string
  expires_at?: string
  is_expired: boolean
}

export interface JobListResponse {
  items: JobListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const jobsApi = {
  getJobs: (page: number = 1, pageSize: number = 20) =>
    apiClient.get<JobListResponse>('/jobs', { params: { page, page_size: pageSize } }),

  getJobDetail: (jobId: number) =>
    apiClient.get<JobDetail>(`/jobs/${jobId}`),
}
```

#### 2.6 Job 列表页面

**src/features/jobs/JobListPage.tsx**:
```typescript
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobsApi } from '@/api/jobs'
import { formatDistanceToNow } from 'date-fns'

export default function JobListPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useQuery({
    queryKey: ['jobs', page],
    queryFn: () => jobsApi.getJobs(page).then((res) => res.data),
  })

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <p className="text-gray-500">Loading jobs...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex justify-center items-center h-64">
        <p className="text-red-500">Failed to load jobs</p>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Job Opportunities</h1>
        <p className="text-gray-600 mt-2">
          Total {data?.total} jobs available
        </p>
      </div>

      <div className="space-y-4">
        {data?.items.map((job) => (
          <Link
            key={job.id}
            to={`/jobs/${job.id}`}
            className="block bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <h2 className="text-xl font-semibold text-gray-900 hover:text-blue-600">
                  {job.title}
                </h2>
                <p className="text-gray-600 mt-1">{job.company_name}</p>
                <div className="flex gap-4 mt-2 text-sm text-gray-500">
                  {job.location_label && <span>📍 {job.location_label}</span>}
                  {job.work_types_label && <span>💼 {job.work_types_label}</span>}
                  {job.salary_label && <span>💰 {job.salary_label}</span>}
                </div>
                {job.abstract && (
                  <p className="text-gray-700 mt-3 line-clamp-2">{job.abstract}</p>
                )}
              </div>
              {job.listed_at && (
                <span className="text-sm text-gray-500 ml-4">
                  {formatDistanceToNow(new Date(job.listed_at), { addSuffix: true })}
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>

      {/* Pagination */}
      <div className="mt-8 flex justify-center gap-2">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-4 py-2 border border-gray-300 rounded-md disabled:opacity-50 hover:bg-gray-50"
        >
          Previous
        </button>
        <span className="px-4 py-2">
          Page {page} of {data?.total_pages}
        </span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={page === data?.total_pages}
          className="px-4 py-2 border border-gray-300 rounded-md disabled:opacity-50 hover:bg-gray-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
```

#### 2.7 Job 详情页面

**src/features/jobs/JobDetailPage.tsx**:
```typescript
import { useQuery } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { jobsApi } from '@/api/jobs'
import { format } from 'date-fns'

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()

  const { data: job, isLoading, error } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.getJobDetail(Number(jobId)).then((res) => res.data),
    enabled: !!jobId,
  })

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <p className="text-gray-500">Loading job details...</p>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="flex justify-center items-center h-64">
        <p className="text-red-500">Job not found</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <Link to="/jobs" className="text-blue-600 hover:text-blue-800 mb-4 inline-block">
        ← Back to Jobs
      </Link>

      <div className="bg-white border border-gray-200 rounded-lg p-8">
        <h1 className="text-3xl font-bold text-gray-900">{job.title}</h1>

        <div className="mt-4 flex flex-wrap gap-4 text-gray-600">
          {job.company_name && <span className="font-medium">{job.company_name}</span>}
          {job.location_label && <span>📍 {job.location_label}</span>}
          {job.work_types_label && <span>💼 {job.work_types_label}</span>}
          {job.salary_label && <span>💰 {job.salary_label}</span>}
        </div>

        {job.classification && (
          <div className="mt-4 flex gap-2">
            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
              {job.classification}
            </span>
            {job.sub_classification && (
              <span className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm">
                {job.sub_classification}
              </span>
            )}
          </div>
        )}

        {job.abstract && (
          <div className="mt-6">
            <h2 className="text-xl font-semibold text-gray-900">Summary</h2>
            <p className="mt-2 text-gray-700">{job.abstract}</p>
          </div>
        )}

        {job.content && (
          <div className="mt-6">
            <h2 className="text-xl font-semibold text-gray-900">Description</h2>
            <div className="mt-2 text-gray-700 whitespace-pre-wrap">
              {job.content}
            </div>
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-500">
              {job.listed_at && (
                <p>Posted: {format(new Date(job.listed_at), 'PPP')}</p>
              )}
              {job.expires_at && (
                <p>Expires: {format(new Date(job.expires_at), 'PPP')}</p>
              )}
            </div>

            <button className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              Apply Now (Coming Soon)
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
```

#### 2.8 更新路由

**src/router.tsx** (更新):
```typescript
import JobListPage from '@/features/jobs/JobListPage'
import JobDetailPage from '@/features/jobs/JobDetailPage'

// Add to router:
{
  path: '/jobs',
  element: (
    <ProtectedRoute>
      <JobListPage />
    </ProtectedRoute>
  ),
},
{
  path: '/jobs/:jobId',
  element: (
    <ProtectedRoute>
      <JobDetailPage />
    </ProtectedRoute>
  ),
},
```

### 联调测试 🧪

#### 测试流程:
1. 登录系统
2. 查看 Job 列表（确保数据库有数据）
3. 点击 Job 卡片查看详情
4. 测试分页功能

### 验收标准 ✅

- [ ] Job 列表页正确显示所有 Job
- [ ] 显示公司、地点、薪资等核心信息
- [ ] 分页功能正常（上一页/下一页）
- [ ] 点击 Job 跳转到详情页
- [ ] 详情页显示完整 Job 信息
- [ ] 加载状态和错误提示正确显示
- [ ] 未登录用户无法访问 Job 页面

### 预估时间: 3-4 小时

---

## Stage 3: 简历管理模块 📝

### 目标
用户可以创建、编辑简历，切换草稿/正式状态，并查看简历列表。

### 后端任务 (Backend)

#### 3.1 数据模型

**app/modules/resumes/models.py**:
```python
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import uuid4
from app.shared.base_model import Base, TimestampMixin

class DocumentFormat(str, Enum):
    Markdown = "Markdown"
    HTML = "HTML"
    PlainText = "PlainText"

class Document(Base, TimestampMixin):
    """Document content with version chain"""
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    root_id: Mapped[str] = mapped_column(String, nullable=False)  # Document family root
    parent_id: Mapped[str | None] = mapped_column(String, ForeignKey("documents.id", ondelete="SET NULL"))
    format: Mapped[DocumentFormat] = mapped_column(
        SQLEnum(DocumentFormat, native_enum=False),
        default=DocumentFormat.Markdown
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hash
    change_comments: Mapped[str | None] = mapped_column(Text)  # Version change notes
    metadata: Mapped[dict | None] = mapped_column(JSON)  # Business metadata
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    # Relationships
    parent = relationship("Document", remote_side=[id], foreign_keys=[parent_id])
    creator = relationship("User", foreign_keys=[created_by])

class Resume(Base, TimestampMixin):
    """Resume metadata"""
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="resumes")
    document = relationship("Document")
```

**app/modules/auth/models.py** (更新 User 模型):
```python
# Add to User model:
resumes = relationship("Resume", back_populates="user")
```

#### 3.2 Schemas

**app/modules/resumes/schemas.py**:
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DocumentCreate(BaseModel):
    """Create document request"""
    content: str
    format: str = "Markdown"
    change_comments: Optional[str] = None

class DocumentResponse(BaseModel):
    """Document response"""
    id: str
    root_id: str
    parent_id: Optional[str]
    format: str
    content: str
    content_hash: str
    change_comments: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ResumeCreate(BaseModel):
    """Create resume request"""
    title: str
    content: str
    is_draft: bool = True

class ResumeUpdate(BaseModel):
    """Update resume request"""
    title: Optional[str] = None
    content: Optional[str] = None
    is_draft: Optional[bool] = None
    change_comments: Optional[str] = None

class ResumeListItem(BaseModel):
    """Resume list item"""
    id: str
    title: str
    is_draft: bool
    updated_at: datetime

    class Config:
        from_attributes = True

class ResumeDetail(BaseModel):
    """Resume detail response"""
    id: str
    user_id: str
    title: str
    is_draft: bool
    document: DocumentResponse
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

#### 3.3 Service 层

**app/modules/resumes/service.py**:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import HTTPException, status
from hashlib import sha256
from uuid import uuid4

from app.modules.resumes.models import Resume, Document, DocumentFormat
from app.modules.resumes.schemas import ResumeCreate, ResumeUpdate, ResumeListItem, ResumeDetail

class ResumeService:
    @staticmethod
    def _hash_content(content: str) -> str:
        """Generate SHA256 hash of content"""
        return sha256(content.encode()).hexdigest()

    @staticmethod
    async def create_resume(
        db: AsyncSession,
        user_id: str,
        resume_data: ResumeCreate
    ) -> ResumeDetail:
        """Create new resume with initial document"""
        # Create root document
        document_id = str(uuid4())
        document = Document(
            id=document_id,
            root_id=document_id,  # Self-reference for root
            parent_id=None,
            format=DocumentFormat.Markdown,
            content=resume_data.content,
            content_hash=ResumeService._hash_content(resume_data.content),
            created_by=user_id
        )
        db.add(document)

        # Create resume
        resume = Resume(
            id=str(uuid4()),
            user_id=user_id,
            document_id=document_id,
            title=resume_data.title,
            is_draft=resume_data.is_draft
        )
        db.add(resume)

        await db.commit()
        await db.refresh(resume)
        await db.refresh(document)

        return ResumeDetail.model_validate(resume)

    @staticmethod
    async def get_user_resumes(db: AsyncSession, user_id: str) -> list[ResumeListItem]:
        """Get all resumes for a user"""
        stmt = (
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(desc(Resume.updated_at))
        )
        result = await db.execute(stmt)
        resumes = result.scalars().all()

        return [ResumeListItem.model_validate(r) for r in resumes]

    @staticmethod
    async def get_resume_detail(
        db: AsyncSession,
        resume_id: str,
        user_id: str
    ) -> ResumeDetail | None:
        """Get resume detail"""
        stmt = (
            select(Resume)
            .where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        result = await db.execute(stmt)
        resume = result.scalar_one_or_none()

        if resume:
            return ResumeDetail.model_validate(resume)
        return None

    @staticmethod
    async def update_resume(
        db: AsyncSession,
        resume_id: str,
        user_id: str,
        update_data: ResumeUpdate
    ) -> ResumeDetail:
        """Update resume (creates new document version if content changed)"""
        # Get existing resume
        stmt = select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        result = await db.execute(stmt)
        resume = result.scalar_one_or_none()

        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Update title and draft status
        if update_data.title is not None:
            resume.title = update_data.title
        if update_data.is_draft is not None:
            resume.is_draft = update_data.is_draft

        # If content changed, create new document version
        if update_data.content is not None:
            # Get current document
            current_doc_stmt = select(Document).where(Document.id == resume.document_id)
            current_doc_result = await db.execute(current_doc_stmt)
            current_doc = current_doc_result.scalar_one()

            new_content_hash = ResumeService._hash_content(update_data.content)

            # Only create new version if content actually changed
            if new_content_hash != current_doc.content_hash:
                new_document = Document(
                    id=str(uuid4()),
                    root_id=current_doc.root_id,  # Same family
                    parent_id=current_doc.id,      # Point to previous version
                    format=current_doc.format,
                    content=update_data.content,
                    content_hash=new_content_hash,
                    change_comments=update_data.change_comments,
                    created_by=user_id
                )
                db.add(new_document)
                await db.flush()

                # Update resume to point to new document
                resume.document_id = new_document.id

        await db.commit()
        await db.refresh(resume)

        return ResumeDetail.model_validate(resume)

    @staticmethod
    async def delete_resume(db: AsyncSession, resume_id: str, user_id: str) -> bool:
        """Delete resume (hard delete for v0.1, soft delete in v0.5)"""
        stmt = select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        result = await db.execute(stmt)
        resume = result.scalar_one_or_none()

        if not resume:
            return False

        await db.delete(resume)
        await db.commit()
        return True
```

#### 3.4 Router

**app/modules/resumes/router.py**:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.resumes.schemas import (
    ResumeCreate, ResumeUpdate, ResumeListItem, ResumeDetail
)
from app.modules.resumes.service import ResumeService

router = APIRouter(prefix="/resumes", tags=["Resumes"])

@router.post("", response_model=ResumeDetail, status_code=201)
async def create_resume(
    resume_data: ResumeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new resume"""
    return await ResumeService.create_resume(db, current_user.id, resume_data)

@router.get("", response_model=list[ResumeListItem])
async def get_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all resumes for current user"""
    return await ResumeService.get_user_resumes(db, current_user.id)

@router.get("/{resume_id}", response_model=ResumeDetail)
async def get_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get resume detail"""
    resume = await ResumeService.get_resume_detail(db, resume_id, current_user.id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume

@router.patch("/{resume_id}", response_model=ResumeDetail)
async def update_resume(
    resume_id: str,
    update_data: ResumeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update resume"""
    return await ResumeService.update_resume(db, resume_id, current_user.id, update_data)

@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete resume"""
    success = await ResumeService.delete_resume(db, resume_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Resume not found")
```

**app/api/v1/router.py** (更新):
```python
from app.modules.resumes.router import router as resumes_router

api_router.include_router(resumes_router)
```

### 前端任务 (Frontend)

#### 3.5 Resume API 封装

**src/api/resumes.ts**:
```typescript
import apiClient from './client'

export interface ResumeCreate {
  title: string
  content: string
  is_draft: boolean
}

export interface ResumeUpdate {
  title?: string
  content?: string
  is_draft?: boolean
  change_comments?: string
}

export interface ResumeListItem {
  id: string
  title: string
  is_draft: boolean
  updated_at: string
}

export interface DocumentResponse {
  id: string
  root_id: string
  parent_id?: string
  format: string
  content: string
  content_hash: string
  change_comments?: string
  created_at: string
}

export interface ResumeDetail {
  id: string
  user_id: string
  title: string
  is_draft: boolean
  document: DocumentResponse
  created_at: string
  updated_at: string
}

export const resumesApi = {
  createResume: (data: ResumeCreate) =>
    apiClient.post<ResumeDetail>('/resumes', data),

  getResumes: () =>
    apiClient.get<ResumeListItem[]>('/resumes'),

  getResumeDetail: (resumeId: string) =>
    apiClient.get<ResumeDetail>(`/resumes/${resumeId}`),

  updateResume: (resumeId: string, data: ResumeUpdate) =>
    apiClient.patch<ResumeDetail>(`/resumes/${resumeId}`, data),

  deleteResume: (resumeId: string) =>
    apiClient.delete(`/resumes/${resumeId}`),
}
```

#### 3.6 简历列表页面

**src/features/resumes/ResumeListPage.tsx**:
```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { resumesApi } from '@/api/resumes'
import { formatDistanceToNow } from 'date-fns'

export default function ResumeListPage() {
  const queryClient = useQueryClient()

  const { data: resumes, isLoading } = useQuery({
    queryKey: ['resumes'],
    queryFn: () => resumesApi.getResumes().then((res) => res.data),
  })

  const deleteMutation = useMutation({
    mutationFn: resumesApi.deleteResume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
  })

  const handleDelete = (resumeId: string, title: string) => {
    if (window.confirm(`Are you sure you want to delete "${title}"?`)) {
      deleteMutation.mutate(resumeId)
    }
  }

  if (isLoading) {
    return <div className="flex justify-center items-center h-64">Loading...</div>
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">My Resumes</h1>
        <Link
          to="/resumes/new"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          + New Resume
        </Link>
      </div>

      {resumes && resumes.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p>No resumes yet. Create your first one!</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {resumes?.map((resume) => (
          <div
            key={resume.id}
            className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex justify-between items-start mb-3">
              <h3 className="text-lg font-semibold text-gray-900">{resume.title}</h3>
              {resume.is_draft ? (
                <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded">
                  Draft
                </span>
              ) : (
                <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                  Final
                </span>
              )}
            </div>

            <p className="text-sm text-gray-500 mb-4">
              Updated {formatDistanceToNow(new Date(resume.updated_at), { addSuffix: true })}
            </p>

            <div className="flex gap-2">
              <Link
                to={`/resumes/${resume.id}`}
                className="flex-1 text-center px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
              >
                Edit
              </Link>
              <button
                onClick={() => handleDelete(resume.id, resume.title)}
                className="px-3 py-2 border border-red-300 text-red-600 rounded-md text-sm hover:bg-red-50"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

#### 3.7 简历编辑器页面

**src/features/resumes/ResumeEditorPage.tsx**:
```typescript
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { resumesApi, ResumeCreate, ResumeUpdate } from '@/api/resumes'

export default function ResumeEditorPage() {
  const { resumeId } = useParams<{ resumeId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isNew = resumeId === 'new'

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [isDraft, setIsDraft] = useState(true)
  const [changeComments, setChangeComments] = useState('')

  // Load existing resume
  const { data: resume } = useQuery({
    queryKey: ['resume', resumeId],
    queryFn: () => resumesApi.getResumeDetail(resumeId!).then((res) => res.data),
    enabled: !isNew && !!resumeId,
  })

  useEffect(() => {
    if (resume) {
      setTitle(resume.title)
      setContent(resume.document.content)
      setIsDraft(resume.is_draft)
    }
  }, [resume])

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: ResumeCreate) => resumesApi.createResume(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      navigate('/resumes')
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: ResumeUpdate) => resumesApi.updateResume(resumeId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      queryClient.invalidateQueries({ queryKey: ['resume', resumeId] })
      alert('Resume updated successfully!')
    },
  })

  const handleSave = () => {
    if (!title.trim()) {
      alert('Please enter a title')
      return
    }

    if (isNew) {
      createMutation.mutate({ title, content, is_draft: isDraft })
    } else {
      updateMutation.mutate({
        title,
        content,
        is_draft: isDraft,
        change_comments: changeComments || undefined,
      })
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          {isNew ? 'Create New Resume' : 'Edit Resume'}
        </h1>
      </div>

      <div className="space-y-6">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Resume Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Software Engineer Resume"
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Draft/Final Toggle */}
        <div className="flex items-center gap-4">
          <label className="flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={!isDraft}
              onChange={(e) => setIsDraft(!e.target.checked)}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">
              Mark as Final Version
            </span>
          </label>
          {!isDraft && (
            <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
              Final
            </span>
          )}
        </div>

        {/* Content Editor */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Content (Markdown)
          </label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={20}
            placeholder="Write your resume in Markdown format..."
            className="w-full px-4 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Change Comments (for updates) */}
        {!isNew && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Change Comments (Optional)
            </label>
            <input
              type="text"
              value={changeComments}
              onChange={(e) => setChangeComments(e.target.value)}
              placeholder="Describe what changed in this version..."
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={handleSave}
            disabled={createMutation.isPending || updateMutation.isPending}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {createMutation.isPending || updateMutation.isPending
              ? 'Saving...'
              : 'Save Resume'}
          </button>
          <button
            onClick={() => navigate('/resumes')}
            className="px-6 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
```

#### 3.8 更新路由

**src/router.tsx** (更新):
```typescript
import ResumeListPage from '@/features/resumes/ResumeListPage'
import ResumeEditorPage from '@/features/resumes/ResumeEditorPage'

// Add to router:
{
  path: '/resumes',
  element: (
    <ProtectedRoute>
      <ResumeListPage />
    </ProtectedRoute>
  ),
},
{
  path: '/resumes/:resumeId',
  element: (
    <ProtectedRoute>
      <ResumeEditorPage />
    </ProtectedRoute>
  ),
},
```

### 联调测试 🧪

#### 测试流程:
1. 访问简历列表页
2. 创建新简历
3. 编辑简历内容
4. 切换草稿/正式状态
5. 更新简历（验证新版本创建）
6. 删除简历

### 验收标准 ✅

- [ ] 用户可以创建新简历
- [ ] 简历列表正确显示所有简历
- [ ] 可以编辑已有简历
- [ ] 编辑后创建新 Document 版本
- [ ] 可以切换草稿/正式状态
- [ ] 可以删除简历
- [ ] 显示更新时间和状态标签
- [ ] 版本链正确（parent_id 指向上一版本）

### 预估时间: 5-6 小时

---

## Stage 4-7: 后续阶段概要

由于文档长度限制，Stage 4-7 将简化描述关键功能点：

### Stage 4: AI Agent 基础 🤖 (4-5 小时)
- **后端**: OpenAI 集成 + tailor_resume + generate_cover_letter Agent
- **前端**: 测试页面（可选）
- **验收**: 调用 AI 生成定制简历和求职信

### Stage 5: 申请创建与工作流 ⚙️ (5-6 小时)
- **后端**: Application 模型 + Celery 串行工作流
- **前端**: 申请创建流程（选择简历 + Job）
- **验收**: 创建申请后自动触发 AI 工作流

### Stage 6: 申请管理与材料查看 📊 (4-5 小时)
- **后端**: 申请列表/详情 API + PDF 生成
- **前端**: 申请列表页 + 材料查看/下载
- **验收**: 查看定制简历和求职信，下载 PDF

### Stage 7: 系统集成与优化 🚀 (3-4 小时)
- 错误处理优化
- 加载状态优化
- 数据验证增强
- 完整端到端测试

---

## 总体时间估算

| Stage | 描述 | 时间 | 累计 |
|-------|------|------|------|
| Stage 0 | 项目初始化 | 2-3h | 3h |
| Stage 1 | 认证系统 | 4-5h | 8h |
| Stage 2 | Job 浏览 | 3-4h | 12h |
| Stage 3 | 简历管理 | 5-6h | 18h |
| Stage 4 | AI Agent | 4-5h | 23h |
| Stage 5 | 申请工作流 | 5-6h | 29h |
| Stage 6 | 申请管理 | 4-5h | 34h |
| Stage 7 | 系统优化 | 3-4h | 38h |

**总计**: 约 35-40 小时 (4-5 个工作日)

---

## 开发环境要求

### 后端
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Poetry

### 前端
- Node.js 18+
- npm/pnpm

### 外部服务
- OpenAI API Key (或 spec-kit Gateway)

---

## 每日开发建议

### Day 1: 基础设施
- Stage 0: 项目初始化
- Stage 1: 认证系统

### Day 2: 核心功能
- Stage 2: Job 浏览
- Stage 3: 简历管理（前半部分）

### Day 3: 简历与 AI
- Stage 3: 简历管理（后半部分）
- Stage 4: AI Agent 基础

### Day 4: 工作流
- Stage 5: 申请创建与工作流
- Stage 6: 申请管理（前半部分）

### Day 5: 完善与测试
- Stage 6: 申请管理（后半部分）
- Stage 7: 系统集成与优化

---

## 注意事项

1. **数据库迁移**: 每个 Stage 完成后执行 `alembic revision --autogenerate`
2. **代码提交**: 每个 Stage 完成后提交 Git（独立可回滚）
3. **测试优先**: 每个 API 先用 Postman 测试，再集成前端
4. **错误处理**: 前端必须处理所有可能的错误状态
5. **类型安全**: 前后端严格遵循 TypeScript/Pydantic 类型定义

---

## 下一步行动

**建议从 Stage 0 开始执行。准备好后，我可以帮助你：**

1. 生成具体的代码文件
2. 配置开发环境
3. 解决技术问题
4. 优化实现方案

**你希望我现在开始 Stage 0 的实施吗？**
