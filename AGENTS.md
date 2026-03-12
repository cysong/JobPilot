# AI Agents Development Workflow

This file defines the development workflow and documentation standards for the JobPilot project.

---

## Project Context

**Project:** JobPilot - AI-powered job application assistant
**Tech Stack:** FastAPI + React + PostgreSQL + Redis + OpenAI
**Development Approach:** Incremental, milestone-based development
**Package Managers:** `uv` (Python) + `pnpm` (Node.js)

---

## Required Reading

Before starting any task, review these documents:

### Planning & Design
- **[Requirements](docs/requirements.md)** - Feature specifications
- **[UI Design Requirements](docs/ui_design_requirements.md)** - UI/UX guidelines
- **[Architecture](docs/architecture.md)** - System architecture
- **[Execution Plan](docs/plan.md)** - Milestone roadmap (v0.1 - v2.0)
- **[UI Prototypes](docs/prototypes/)** - Design references

### Development Tracking
- **[Development Progress](docs/progress.md)** - Work log and current status
- **[Issues & Fixes](docs/issues.md)** - Problem tracking

---

## Project Structure

### Backend Structure
```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── core/                # Core functionality
│   │   ├── config.py        # Pydantic Settings configuration
│   │   ├── database.py      # Async SQLAlchemy setup
│   │   ├── security.py      # JWT and password hashing
│   │   └── exceptions.py    # Global exception handlers
│   ├── shared/              # Shared utilities
│   │   ├── base_model.py    # SQLAlchemy base models
│   │   ├── enums.py         # Global enums
│   │   └── pagination.py    # Pagination utilities
│   ├── api/                 # API routes
│   │   └── v1/
│   │       ├── __init__.py  # API v1 router
│   │       └── endpoints/   # Endpoint modules
│   └── modules/             # Business modules
│       └── [module_name]/
│           ├── models.py    # SQLAlchemy models
│           ├── schemas.py   # Pydantic schemas
│           ├── service.py   # Business logic
│           └── router.py    # API endpoints
├── alembic/                 # Database migrations
│   ├── env.py              # Alembic async config
│   └── versions/           # Migration files
├── pyproject.toml          # uv dependencies
└── .env                    # Environment variables
```

### Frontend Structure
```
frontend/
├── src/
│   ├── main.tsx            # Application entry point
│   ├── App.tsx             # Root component
│   ├── index.css           # Tailwind CSS imports
│   ├── api/                # API clients
│   │   ├── client.ts       # Axios instance with interceptors
│   │   └── [module].ts     # Module-specific API calls
│   ├── components/         # Shared UI components
│   │   └── [Component]/
│   │       ├── index.tsx
│   │       └── styles.css
│   ├── features/           # Feature modules
│   │   └── [feature]/
│   │       ├── components/ # Feature-specific components
│   │       ├── hooks/      # Feature-specific hooks
│   │       └── types.ts    # Feature types
│   ├── hooks/              # Shared React hooks
│   ├── store/              # Zustand stores
│   │   └── [store].ts
│   ├── types/              # TypeScript types
│   ├── utils/              # Utility functions
│   └── pages/              # Page components
│       └── [Page].tsx
├── vite.config.ts          # Vite configuration
├── tsconfig.json           # TypeScript configuration
├── postcss.config.js       # PostCSS with Tailwind v4
└── package.json            # pnpm dependencies
```

---

## Development Workflow

### Phase 1: Planning & Design Review

When starting a new milestone or feature:

1. **Review Requirements**
   - Read relevant sections in requirements.md
   - Check UI design requirements
   - Review workflow design for the feature
   - Check UI prototypes if available

2. **Create Implementation Plan**
   - Break down milestone into concrete tasks
   - Identify files to create/modify
   - Document technical decisions
   - List backend and frontend tasks separately
   - **Present plan and wait for user confirmation**

3. **Document the Plan**
   - Create detailed execution plan in docs if required
   - List all tasks with clear descriptions
   - Get user approval before proceeding

### Phase 2: Implementation

1. **Execute Code Changes**
   - Follow existing code patterns
   - Implement one task at a time
   - Write clean, maintainable code
   - Add comments for complex logic (in English)

2. **Track Problems**
   - If you encounter an issue, document it in [docs/issues.md](docs/issues.md)
   - Include: problem description, root cause, solution steps, verification
   - Update with resolution once fixed

3. **Test Changes**
   - Verify functionality works as expected
   - Test edge cases
   - Ensure no regressions

### Phase 3: Documentation & Completion

1. **Update Progress Log**
   - Record completed tasks in [docs/progress.md](docs/progress.md)
   - Use date-based entries (YYYY-MM-DD format)
   - List all completed tasks under the date
   - Update "Next Steps" section

2. **Update Design Documents (if needed)**
   - If implementation differs from design, update docs
   - **Always create update plan first and get user confirmation**
   - Affected docs: architecture.md, workflow-design.md, etc.
   - Keep documentation in sync with code

3. **Record Knowledge (when requested)**
   - Document new techniques in [docs/notes.md](docs/notes.md)
   - Include: what was learned, why it's useful, examples
   - Only when user explicitly requests it

---

## How to Add New Features

### Adding a New Backend Module

1. **Create Module Directory**
   ```
   backend/app/modules/[module_name]/
   ├── models.py      # SQLAlchemy models
   ├── schemas.py     # Pydantic request/response schemas
   ├── service.py     # Business logic
   └── router.py      # FastAPI endpoints
   ```

2. **Define Models** (`models.py`)
   ```python
   from app.shared.base_model import Base, TimestampMixin

   class YourModel(Base, TimestampMixin):
       __tablename__ = "your_table"
       # fields...
   ```

3. **Define Schemas** (`schemas.py`)
   ```python
   from pydantic import BaseModel

   class YourSchema(BaseModel):
       # fields...

       class Config:
           from_attributes = True
   ```

4. **Implement Service** (`service.py`)
   ```python
   from sqlalchemy.ext.asyncio import AsyncSession

   async def get_items(db: AsyncSession):
       # business logic...
   ```

5. **Create Router** (`router.py`)
   ```python
   from fastapi import APIRouter, Depends
   from app.core.database import get_db

   router = APIRouter(prefix="/items", tags=["items"])

   @router.get("/")
   async def list_items(db: AsyncSession = Depends(get_db)):
       # endpoint logic...
   ```

6. **Register Router** (in `app/api/v1/__init__.py`)
   ```python
   from app.modules.your_module.router import router as your_router
   api_router.include_router(your_router)
   ```

7. **Create Migration**
   ```bash
   cd backend
   uv run alembic revision --autogenerate -m "Add your_table"
   uv run alembic upgrade head
   ```

### Adding a New Frontend Feature

1. **Create Feature Directory**
   ```
   frontend/src/features/[feature_name]/
   ├── components/       # Feature components
   ├── hooks/           # Feature hooks
   ├── types.ts         # TypeScript types
   └── index.ts         # Public exports
   ```

2. **Create API Client** (`src/api/[module].ts`)
   ```typescript
   import apiClient from './client'

   export const moduleApi = {
     getItems: () => apiClient.get('/items'),
     createItem: (data) => apiClient.post('/items', data),
   }
   ```

3. **Create React Query Hook** (`features/[feature]/hooks/useItems.ts`)
   ```typescript
   import { useQuery } from '@tanstack/react-query'
   import { moduleApi } from '@/api/module'

   export const useItems = () => {
     return useQuery({
       queryKey: ['items'],
       queryFn: moduleApi.getItems,
     })
   }
   ```

4. **Create Zustand Store if needed** (`src/store/[store].ts`)
   ```typescript
   import { create } from 'zustand'

   interface YourStore {
     // state and actions
   }

   export const useYourStore = create<YourStore>((set) => ({
     // implementation
   }))
   ```

5. **Create Components**
   ```typescript
   // features/[feature]/components/YourComponent.tsx
   import { useItems } from '../hooks/useItems'

   export const YourComponent = () => {
     const { data, isLoading } = useItems()
     // component logic...
   }
   ```

6. **Add Route** (in `App.tsx` or routing config)
   ```typescript
   import { YourPage } from '@/pages/YourPage'

   <Route path="/your-path" element={<YourPage />} />
   ```

### Adding a New API Endpoint

**Backend:**
1. Add endpoint to existing router or create new one
2. Define Pydantic schemas for request/response
3. Implement service layer logic
4. Add proper error handling
5. Document with OpenAPI annotations

**Frontend:**
1. Add API call to corresponding API client
2. Create React Query hook (or mutation)
3. Use in component with proper loading/error states

---

## Documentation Standards

### docs/progress.md
- **Purpose:** Work log with completed tasks by date
- **Format:** Date → Completed Tasks → Next Steps
- **Update Frequency:** After completing each milestone/stage

### docs/issues.md
- **Purpose:** Track problems and solutions
- **Format:** Problem → Root Cause → Solution → Verification
- **Update Frequency:** When encountering and fixing issues

### docs/notes.md
- **Purpose:** Knowledge base of learned techniques
- **Format:** Topic → Explanation → Examples
- **Update Frequency:** When user requests knowledge documentation

### Design Documents
- **Purpose:** Keep architecture and design specs current
- **Update Rule:** Always propose changes before updating
- **Affected Files:** architecture.md, requirements.md, etc.

---

## Code Style & Conventions

### Backend (Python)
- **Naming:** snake_case for variables/functions, PascalCase for classes
- **Type Hints:** Always use type hints
- **Async/Await:** Use async for all database operations
- **Comments:** English only, explain WHY not WHAT
- **Imports:** Absolute imports from `app.*`

### Frontend (TypeScript)
- **Naming:** camelCase for variables/functions, PascalCase for components/types
- **Components:** Functional components with hooks
- **Styling:** Tailwind CSS v4 utility classes
- **Imports:** Use `@/` path alias
- **Comments:** English only

### Tailwind CSS v4 Notes
- Use `@import "tailwindcss"` (not `@tailwind` directives)
- Wrap custom styles in `@layer` directives
- Use `@theme` for theme customization
- Built-in autoprefixer, no need for separate plugin

---

## Task Management Principles

1. **One Task at a Time**: Complete and verify before moving to next
2. **Confirm Before Major Changes**: Get user approval for plans
3. **Document Issues Immediately**: Don't wait until end of task
4. **Keep Docs in Sync**: Update documentation when code changes design
5. **Simple and Clear**: Prioritize clarity over cleverness
6. **Test Thoroughly**: Verify each change before committing

---

## Common Commands

### Backend
```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # macOS/Linux

# Install dependencies
uv sync --group dev

# Run development server
uv run uvicorn app.main:app --reload

# Create migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Run tests
uv run pytest
```

### Frontend
```bash
# Install dependencies
pnpm install

# Run development server
pnpm run dev

# Build for production
pnpm run build

# Type check
pnpm run type-check

# Lint
pnpm run lint
```

---

## Key Reminders

**Do:**
- ✅ Always read relevant docs before starting
- ✅ Create implementation plan and get confirmation
- ✅ Document issues as they occur
- ✅ Update progress.md after completing tasks
- ✅ Propose doc updates before making changes
- ✅ Follow existing code patterns
- ✅ Write comments in English
- ✅ Test changes thoroughly

**Don't:**
- ❌ Skip planning phase
- ❌ Update design docs without user approval
- ❌ Batch multiple unrelated changes
- ❌ Commit without testing
- ❌ Ignore existing code patterns
- ❌ Write comments in Chinese (code comments must be English)

---

## Troubleshooting

### Common Issues

**Backend:**
- Database connection errors → Check .env DATABASE_URL
- Migration conflicts → Review alembic versions
- Import errors → Check Python path and virtual environment

**Frontend:**
- Build errors → Check node_modules, try `pnpm install`
- API errors → Verify backend is running and CORS settings
- Type errors → Run `pnpm run type-check`

**Tailwind CSS v4:**
- Styles not applying → Check `@import "tailwindcss"` in index.css
- Build errors → Ensure `@tailwindcss/postcss` is installed
- Custom styles not working → Wrap in `@layer` directive

---

**Last Updated:** 2025-01-23
