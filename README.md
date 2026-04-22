# JobPilot

AI-powered job application assistant that automates resume tailoring and application tracking.

## Features

- Smart job matching with AI-powered skill analysis
- Automated resume customization for each position
- AI-generated tailored cover letters
- Kanban-style application tracking
- Interview preparation materials generation

## Tech Stack

**Backend:** FastAPI • Python 3.11+ • PostgreSQL • Redis • Celery • OpenAI
**Frontend:** React 18 • TypeScript • Vite • Tailwind CSS • Zustand • React Query

## Prerequisites

- Python 3.11+, Node.js 18+
- PostgreSQL 15+, Redis 7+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [pnpm](https://pnpm.io/) (Node.js package manager)

## Quick Start

### Backend Setup

```bash
cd backend

# Copy and configure environment
cp .env.example .env
# Edit .env: DATABASE_URL, SECRET_KEY, OPENAI_API_KEY

# Create virtual environment
uv venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate    # macOS/Linux

# Install dependencies
uv sync --group dev

# Initialize database (see Database Setup section below)

# Start development server
uv run uvicorn app.main:app --reload

# Verify: http://localhost:8000/health
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Database Setup

#### Run Database Migrations

```bash
cd backend

# Apply all migrations
uv run alembic upgrade head

# Verify migration status
uv run alembic current
```

### Database Management

#### Create New Migration

When you modify SQLAlchemy models, create a migration:

```bash
cd backend

# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "description of changes"

# Apply the new migration
uv run alembic upgrade head
```

#### Migration Commands

```bash
# View migration history
uv run alembic history

# Check current migration version
uv run alembic current

# Upgrade to latest version
uv run alembic upgrade head

# Upgrade to specific version
uv run alembic upgrade <revision_id>

# Downgrade one version
uv run alembic downgrade -1

# Downgrade to specific version
uv run alembic downgrade <revision_id>

# Downgrade all migrations
uv run alembic downgrade base
```


### Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Start development server
pnpm run dev

# Verify: http://localhost:5173
```

### Development

Run all services simultaneously:

```bash
# Terminal 1 - Backend API
cd backend
uv run uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend
pnpm run dev

# Terminal 3 - Celery Worker (async tasks)
cd backend
uv run python run_celery_worker.py
# Graceful shutdown for Celery worker
celery -A jobpilot control shutdown

# Terminal 4 - Celery Beat (scheduled tasks)
cd backend
uv run python run_celery_beat.py
```

## Development Roadmap

- [x] **v0.1** - Foundation (Core prototype with end-to-end workflow)
- [ ] **v0.2** - Real-time Feedback (WebSocket progress updates)
- [ ] **v0.3** - Smart Matching (AI-powered job analysis and resume recommendation)
- [ ] **v0.4** - Search & Filter (Advanced job filtering and search)
- [ ] **v0.5** - Application Lifecycle (Complete status workflow and timeline tracking)
- [ ] **v0.6** - Quality Assurance (Automated quality checks and regeneration)
- [ ] **v0.7** - Customization Strategy (Deep/Light tailoring options)
- [ ] **v0.8** - Role & Quota (Multi-role permissions and quota management)
- [ ] **v0.9** - Progress Visualization (Kanban board and statistics)
- [ ] **v1.0** - Interview Preparation (Automated interview prep materials)
- [ ] **v1.1** - Resume Optimization (AI-powered resume analysis and suggestions)
- [ ] **v1.2** - Milestones & Achievements (Gamification elements)
- [ ] **v2.0** - LinkedIn Integration (Networking and referral assistance)

## Conventions

### Enums (DB ↔ backend ↔ frontend)

To prevent silent case-mismatch bugs, every enum that crosses the
storage boundary follows the same shape:

1. **`name == value`, UPPER_SNAKE_CASE.** Python enum members declare
   `FOO = "FOO"`. The display label (`"Phone Screen"`, etc.) lives in
   the frontend, never in the enum value.
2. **Native PostgreSQL `ENUM` type.** Use the `EnumColumn` helper from
   `app/shared/sqlalchemy_helpers.py` — it forces `native_enum=True`
   and `values_callable`, so the DB stores the enum *value* (not the
   Python member name, which historically diverged and broke Pydantic
   reads).
3. **Single PG type, reused across columns.** When two columns hold
   the same enum (e.g. `applications.status` and
   `application_status_history.to_status`), pass the same `name=`
   to `EnumColumn` — they share one PG ENUM type.
4. **Frontend literal union mirrors the value set.** Display labels
   live in a per-component `LABEL_MAP`, not in the type union.
5. **Adding a value:** dedicated alembic migration with
   `ALTER TYPE <name> ADD VALUE 'NEW_VALUE'`. Run outside a
   transaction (`autocommit_block`). Enum values are append-only —
   renames/removals require a full type rebuild and data migration.

`tests/test_enum_columns.py` enforces rule (2) automatically. New
columns missing `values_callable` will fail CI.

## Documentation

Complete specifications and architecture documentation:

- **[Requirements](docs/requirements.md)** - Feature requirements and specifications
- **[UI Design Requirements](docs/ui_design_requirements.md)** - UI/UX design guidelines
- **[Frontend Development Guide](docs/frontend_development_guide.md)** - Frontend workflow, component standards, and styling guidelines
- **[Workflow Design](docs/workflow-design.md)** - Application workflow and state management
- **[Architecture](docs/architecture.md)** - System design and technical decisions
- **[Execution Plan](docs/plan.md)** - Phased milestones and implementation roadmap
- **[Development Progress](docs/progress.md)** - Worklogs and current status
- **[Issues & Fixes](docs/issues.md)** - Problem tracking and solutions

UI prototypes are available in [docs/prototypes/](docs/prototypes/index.html) for design reference.

## Project Structure

```
JobPilot/
├── backend/          # FastAPI REST API
│   ├── app/
│   │   ├── core/     # Configuration & database
│   │   ├── shared/   # Shared utilities
│   │   ├── api/      # API routes
│   │   └── modules/  # Business modules
│   └── alembic/      # Database migrations
├── frontend/         # React SPA
│   └── src/
│       ├── api/      # API clients
│       ├── features/ # Feature modules
│       └── components/ # UI components
└── docs/             # Documentation
```

## License

MIT
