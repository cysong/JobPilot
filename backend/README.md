# JobPilot Backend API

AI-powered job application assistant - Backend API

## Tech Stack

- **Framework**: FastAPI 0.109+
- **Language**: Python 3.11+
- **ORM**: SQLAlchemy 2.0 (Async)
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Task Queue**: Celery + Redis
- **Authentication**: JWT (python-jose)

## Setup

### 1. Install Dependencies

```bash
# Install Poetry if not already installed
# https://python-poetry.org/docs/#installation

# Install dependencies
poetry install
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your actual values
# Especially: DATABASE_URL, SECRET_KEY, OPENAI_API_KEY
```

### 3. Initialize Database

```bash
# Create database
createdb jobpilot

# Run migrations
poetry run alembic upgrade head
```

### 4. Run Development Server

```bash
poetry run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Project Structure

```
backend/
├── app/
│   ├── core/              # Core configurations
│   ├── shared/            # Shared utilities
│   ├── api/               # API routes aggregation
│   └── modules/           # Business modules
├── alembic/               # Database migrations
├── scripts/               # Utility scripts
└── tests/                 # Test files
```

## Development

### Database Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback
poetry run alembic downgrade -1
```

### Code Formatting

```bash
# Format code with black
poetry run black .

# Lint with ruff
poetry run ruff check .
```

### Testing

```bash
poetry run pytest
```

## Version

Current version: **0.1.0**
