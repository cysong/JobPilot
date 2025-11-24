# Development Progress

## Current Status

**Version:** v0.3.0 (Resume Management Module)
**Next Task:** Stage 3 - Application Module

---

## Work Log

### 2025-11-24 - Application Workflow Backend Implemented

**Completed Tasks:**

**Backend Implementation:**
- Added application workflow scaffolding (Celery + workflow/task/outbox/ai_call models) and application API routes for create/get/retry (backend/app/modules/applications/*, backend/app/api/v1/router.py).
- Implemented cover-letter generation task via DeepSeek (OpenRouter) with workflow/task status updates, AI usage logging, and outbox events; added Celery app config (backend/app/core/celery_app.py).
- Updated application schema: status default Pending, source resume + resume/cover documents, soft delete fields, unique (user_id, job_id), last_error, removed workflow_id FK; aligned Alembic migration and architecture doc.
- Added OpenRouter configuration fields; documented backend plan in docs/application-plan.md.

**Pending:**
- Run Alembic migrations to apply updated application/workflow tables.
- Start Celery worker alongside API after setting AI credentials (OPENROUTER_API_KEY or alternatives).

### 2025-11-24 - Resume Management Frontend Completed

**Completed Tasks:**

**Frontend Implementation:**
- ✅ Created TypeScript types (`src/types/resume.ts`) and API client (`src/api/resumes.ts`)
- ✅ Implemented React Query hooks (`src/features/resumes/hooks/useResumes.ts`)
- ✅ Built Resume Management UI:
  - `ResumeListingPage`: Grid view of resumes with create/delete actions
  - `ResumeEditPage`: Split-pane Markdown editor with real-time preview
  - `ResumeCard`: Display resume status (Draft/Formal) and metadata
- ✅ Integrated `react-markdown` for resume preview
- ✅ Implemented PDF export trigger (downloads blob from backend)
- ✅ Configured routes: `/resumes`, `/resumes/new`, `/resumes/:id`

**Refactoring & Optimization:**
- ✅ **Directory Structure**: Standardized `src/features/resumes` (removed `pages` subdirectory)
- ✅ **Configuration**: Fixed `shadcn/ui` alias issue (moved files from `@` to `src`)
- ✅ **Landing Page**: Updated content (removed "AI Cover Letter" badge and trial text)

**Key Features Implemented:**
- Full CRUD for resumes (Create, Read, Update, Delete)
- Draft vs. Formal resume workflow
- Markdown-based resume editing
- Real-time preview
- PDF Export integration

---

### 2025-11-24 - Project Layout & Access Control Completed

**Completed Tasks:**

**Frontend Implementation:**
- ✅ Implemented **Public Layout** (Landing Page) with responsive design
- ✅ Implemented **Main Layout** (Authenticated) with Top Navigation and User Menu
- ✅ Built `Navigation` component with responsive mobile drawer (`Sheet`)
- ✅ Built `UserNav` component with Avatar dropdown and Logout functionality
- ✅ Created `PlaceholderPage` for unimplemented features (Dashboard, Applications, Resumes)
- ✅ Configured `App.tsx` with Public and Protected routes
- ✅ Adapted `JobListingPage` to the new layout structure

**Refactoring & Optimization:**
- ✅ **Directory Structure**: Merged `src/layouts` into `src/components/layout` for a flatter structure
- ✅ **Utility Functions**: Standardized `cn` utility in `src/utils/cn.ts`
- ✅ **Configuration**: Added `components.json` for shadcn/ui and configured path aliases (`@/utils/cn`)
- ✅ **Documentation**: Updated `docs/frontend_development_guide.md` with new structure and standards

**Key Features Implemented:**
- Unified navigation experience for authenticated users
- Modern, responsive Landing Page for public visitors
- Secure access control (redirects to login if unauthenticated)
- Mobile-friendly navigation menu

---

### 2025-11-24 - Document Export System Implemented

**Completed Tasks:**

**Backend Implementation:**
- ✅ Refactored PDF export system to support multiple document types (方案 3: 混合方案)
- ✅ Created **DocumentExportService** - Universal export service ([app/modules/resumes/export/service.py](app/modules/resumes/export/service.py))
  - `export_to_pdf()`: Generic export method for all document types
  - `get_available_document_types()`: Auto-discover document types
  - `get_available_templates(document_type)`: Get templates per type
- ✅ Refactored **PDFGenerator** to support `document_type` parameter ([app/modules/resumes/export/generator.py](app/modules/resumes/export/generator.py))
  - Template path: `templates/{document_type}/{template_name}.html`
  - CSS path: `css/{document_type}/base.css` + `css/{document_type}/{template}.css`
  - Added `get_available_document_types()` method
  - Updated `get_available_templates(document_type)` method
  - Updated `validate_template(document_type, template_name)` method
- ✅ Reorganized template directory structure:
  - `templates/resume/` - Resume templates (modern/classic/minimal)
  - `templates/cover_letter/` - Cover letter templates (to be created)
- ✅ Reorganized CSS directory structure:
  - `css/resume/` - Resume styles (base.css + template-specific)
  - `css/cover_letter/` - Cover letter styles (to be created)
- ✅ Updated **ResumeService** to use DocumentExportService ([app/modules/resumes/service.py](app/modules/resumes/service.py:394-453))
  - Calls `DocumentExportService.export_to_pdf(document_type="resume")`
- ✅ Updated Resume API endpoints ([app/modules/resumes/router.py](app/modules/resumes/router.py))
  - Updated `/resumes/templates` to call `DocumentExportService.get_available_templates("resume")`
- ✅ Updated configuration ([app/core/config.py](app/core/config.py:55))
  - Renamed `RESUME_EXPORT_DEFAULT_TEMPLATE` → `EXPORT_DEFAULT_TEMPLATE`
  - Now applies to all document types

**Documentation:**
- ✅ Updated [docs/resume-export.md](docs/resume-export.md) to reflect new architecture


**Key Features Implemented:**
- Multi-document type support (resume, cover_letter, etc.)
- Template and CSS isolation by document type
- Auto-discovery of document types and templates
- Easy extension: just add new `templates/{type}/` and `css/{type}/` directories
- Backward compatible: existing resume export API unchanged


---

### 2025-11-24 - Resume Management Module Backend Completed

**Completed Tasks:**

**Backend Implementation:**
- ✅ Created Document model with chained version support ([app/modules/resumes/models.py](app/modules/resumes/models.py))
  - Support for Markdown/HTML/PlainText formats
  - Version chain via root_id and parent_id
  - SHA-256 content hashing for deduplication
  - JSON metadata field for extensibility
- ✅ Created Resume model with draft/formal workflow ([app/modules/resumes/models.py](app/modules/resumes/models.py))
  - Soft delete support (is_deleted, deleted_at)
  - One-to-one relationship with Document
  - Draft/formal status tracking
- ✅ Implemented Pydantic schemas ([app/modules/resumes/schemas.py](app/modules/resumes/schemas.py))
  - DocumentBase, DocumentVersion
  - ResumeCreate, ResumeUpdate, ResumeTitleUpdate
  - ResumeResponse, ResumeListItem, ResumeListResponse
  - FormalResumeLimit
- ✅ Built ResumeService with 9 core methods ([app/modules/resumes/service.py](app/modules/resumes/service.py))
  - create_resume(): Creates document + resume with version tracking
  - get_resumes(): Paginated list with draft/formal filtering
  - get_resume_by_id(): Retrieve single resume with document content
  - update_resume(): Creates new document version, updates content
  - update_resume_title(): Title-only update
  - finalize_resume(): Convert draft to formal with quota check (limit: 3)
  - delete_resume(): Soft delete
  - check_formal_resume_limit(): Quota check
  - get_resume_versions(): Version history
- ✅ Created Resume API endpoints ([app/modules/resumes/router.py](app/modules/resumes/router.py))
  - POST /api/v1/resumes - Create resume
  - GET /api/v1/resumes - List resumes (with pagination and filters)
  - GET /api/v1/resumes/formal-limit - Check quota
  - GET /api/v1/resumes/{resume_id} - Get resume detail
  - PUT /api/v1/resumes/{resume_id} - Update content
  - PATCH /api/v1/resumes/{resume_id}/title - Update title
  - PATCH /api/v1/resumes/{resume_id}/finalize - Convert to formal
  - DELETE /api/v1/resumes/{resume_id} - Soft delete
  - GET /api/v1/resumes/{resume_id}/versions - Version history
- ✅ Updated User model to add resume relationships ([app/modules/auth/models.py](app/modules/auth/models.py))
- ✅ Created auth dependencies module ([app/modules/auth/dependencies.py](app/modules/auth/dependencies.py))
- ✅ Registered Resume router in API v1 ([app/api/v1/router.py](app/api/v1/router.py))
- ✅ Generated database migration for resumes and documents tables
  - Migration file: `20251124_0050_2b8ba0e2d92a_add_resumes_and_documents_tables.py`

**Key Features Implemented:**
- Content deduplication via SHA-256 hashing
- Version chain management (root_id → parent_id → children)
- Formal resume quota system (max 3 per user)
- Draft/formal workflow
- Soft delete for resumes
- Full JWT authentication on all endpoints

**Issues Fixed:**
- ✅ Added primary key fields to Document and Resume models
- ✅ Fixed user_id type mismatch (String → int)
- ✅ Fixed JSON column definition (dict → JSON)
- ✅ Renamed reserved field name (metadata → extra_metadata)
- ✅ Cleaned up auto-generated migration (removed unrelated table operations)

**Pending:**
- Apply database migration (user to execute manually)

**Migration Command:**
```bash
cd backend
.venv\Scripts\alembic.exe upgrade head
```

---

### 2025-11-24 - Job Browsing Module Frontend Completed

**Completed Tasks:**

**Frontend Implementation:**
- ✅ Created `docs/frontend_development_guide.md` for development standards
- ✅ Built Core UI components (`Badge`, `Skeleton`, `Separator`, `Sheet`, `Checkbox`, `Select`, `Accordion`, `ScrollArea`)
- ✅ Implemented `JobCard`, `JobSearch`, `JobFilters`, `JobPagination` components
- ✅ Built `JobListingPage` with URL-based state management for filters
- ✅ Built `JobDetailPage` with comprehensive job information display
- ✅ Configured routes for `/jobs` and `/jobs/:jobId`
- ✅ Resolved React Router v7 future flag warnings
- ✅ Refined Auth UI (Alerts for errors, removed custom password strength bars)

**Integration:**
- ✅ Connected Frontend to Backend Job API
- ✅ Verified build success

**Issues Resolved:**
- Fixed TypeScript `import type` errors for build compliance

### 2025-11-24 - Job Browsing Module Backend Completed

**Completed Tasks:**

**Backend Implementation:**
- ✅ Created SeekJob model for read-only access to seek_jobs table (`app/modules/jobs/models.py`)
- ✅ Mapped 70+ fields from external crawler system's seek_jobs table
- ✅ Added database indexes for optimized querying (source_id, title, listed_at, location_city, etc.)
- ✅ Implemented Pydantic schemas for API requests/responses (`app/modules/jobs/schemas.py`)
  - JobBase: List display fields
  - JobDetail: Complete job information
  - JobListResponse: Paginated response format
  - JobFiltersRequest: Filter parameters
  - JobFiltersOptions: Available filter dropdown options
- ✅ Built JobService with core business logic (`app/modules/jobs/service.py`)
  - get_jobs(): Pagination + multi-dimension filtering + full-text search
  - get_job_by_id(): Job detail retrieval
  - get_filter_options(): Dynamic filter options
  - get_similar_jobs(): Same company + classification recommendations
- ✅ Created Job API endpoints (`app/modules/jobs/router.py`)
  - GET /api/v1/jobs - Paginated job list with filters
  - GET /api/v1/jobs/filters - Filter dropdown options
  - GET /api/v1/jobs/{job_id} - Job details
  - GET /api/v1/jobs/{job_id}/similar - Similar jobs
- ✅ Registered Job router in API v1 (`app/api/v1/router.py`)

**Frontend Implementation:**
- ✅ Created TypeScript type definitions (`src/types/job.ts`)
  - Job, JobDetail, JobListResponse, JobFiltersRequest, JobFiltersOptions
- ✅ Built Job API client (`src/api/jobs.ts`)
  - getJobs(), getJobById(), getSimilarJobs(), getFilterOptions()
- ✅ Implemented React Query hooks (`src/features/jobs/hooks/useJobs.ts`)
  - useJobs(), useJobDetail(), useSimilarJobs(), useJobFilterOptions()
- ✅ Added shadcn/ui components
  - Badge component (`src/components/ui/badge.tsx`)
  - Skeleton component (`src/components/ui/skeleton.tsx`)

**Key Features Implemented:**
- Full-text search across title, abstract, and content
- Multi-select filtering (location, work type, company)
- Date range filtering (listed_after/listed_before)
- Sorting by listed_at or title (asc/desc)
- Server-side pagination (configurable page size, max 100)
- Similar job recommendations based on company and classification

---

### 2025-11-23 - Authentication System Completed

**Completed Tasks:**

**Backend Implementation:**
- ✅ Created User model with SQLAlchemy (`app/modules/auth/models.py`)
- ✅ Implemented JWT token generation and validation (`app/core/security.py`)
- ✅ Created password hashing utilities with bcrypt
- ✅ Built authentication service (register, login) (`app/modules/auth/service.py`)
- ✅ Implemented get_current_user dependency
- ✅ Created auth API endpoints (`app/modules/auth/router.py`)
- ✅ Generated and applied Alembic migration for User table
- ✅ Fixed bcrypt compatibility issues (downgraded to 4.0.1)

**Frontend Implementation:**
- ✅ Created auth API client (`src/api/auth.ts`)
- ✅ Implemented Zustand auth store with localStorage persistence (`src/store/authStore.ts`)
- ✅ Built Login page component (`src/pages/Login.tsx`)
- ✅ Built Register page component (`src/pages/Register.tsx`)
- ✅ Set up React Router with protected routes
- ✅ Implemented ProtectedRoute wrapper component
- ✅ Imported shadcn/ui components (Button, Input, Card, Form, Label)

**Integration Testing:**
- ✅ Tested user registration flow
- ✅ Tested user login flow
- ✅ Verified JWT token storage in localStorage
- ✅ Tested protected route access control
- ✅ Verified token-based authentication in API requests

**Issues Resolved:**
- Fixed bcrypt compatibility issue by downgrading from 4.2.1 to 4.0.1
- Resolved circular import warnings in backend modules
- Downgraded Tailwind CSS from v4 to v3.4.18 for better shadcn/ui compatibility

---

### 2025-01-22 - Project Initialization

**Completed Tasks:**

**Backend Setup:**
- Created FastAPI project structure with async SQLAlchemy 2.0
- Configured Alembic for database migrations
- Implemented core configuration with Pydantic Settings
- Created base models and global enums
- Set up CORS middleware and exception handlers
- Added health check endpoint at `/health`

**Frontend Setup:**
- Initialized Vite + React + TypeScript project
- Upgraded to Tailwind CSS v4 with @tailwindcss/postcss
- Configured Axios client with auth interceptors
- Set up TanStack Query (React Query)
- Created project directory structure
- Configured API proxy in Vite

**Infrastructure:**
- Adopted `uv` as Python package manager
- Adopted `pnpm` as Node.js package manager
- Created environment configuration files
- Wrote comprehensive documentation (README.md, TAILWIND-V4.md, FIXES.md)

**Key Changes:**
- Replaced Poetry with `uv` for better performance
- Replaced npm with `pnpm` for faster installs
- Chose Tailwind CSS v4 for modern features

---

## Next Steps

### Stage 3: Application Module
- **Backend**:
  - Design Application model (user_id, job_id, resume_id, status)
  - Create API endpoints for applying to jobs
  - Implement file upload for resumes (if not already done)
- **Frontend**:
  - Build "Apply Now" modal/flow
  - Create "My Applications" page
  - Integrate Resume upload

### Stage 4: User Profile & Settings
- **Frontend**:
  - Build User Profile page
  - Settings page (password change, notification prefs)

## Known Issues

None at this stage.

---

## Technical Notes

- Using Tailwind CSS v3.4.18 with traditional `@tailwind` directives
- Custom styles are wrapped in `@layer` directives for proper CSS ordering
- shadcn/ui components use CSS variables for theming (defined in `src/index.css`)
- Database migrations managed by Alembic (async mode)
- JWT tokens stored in localStorage with automatic axios interceptor injection
- Celery workers will be configured in later stages

---

**Last Updated:** 2025-01-24
