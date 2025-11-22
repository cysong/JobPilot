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

# Run database migrations (after Stage 1)
# uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload

# Verify: http://localhost:8000/health
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
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

Run both services simultaneously:

```bash
# Terminal 1 - Backend
cd backend
uv run uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend
pnpm run dev
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

## Documentation

Complete specifications and architecture documentation:

- **[Requirements](docs/requirements.md)** - Feature requirements and specifications
- **[UI Design Requirements](docs/ui_design_requirements.md)** - UI/UX design guidelines
- **[Workflow Design](docs/workflow-design.md)** - Application workflow and state management
- **[Architecture](docs/architecture.md)** - System design and technical decisions
- **[Execution Plan](docs/plan.md)** - Phased milestones and implementation roadmap
- **[Development Progress](docs/progress.md)** - Worklogs and current status

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
