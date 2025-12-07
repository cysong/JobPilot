"""Celery beat startup script with automatic path configuration."""
import sys
from pathlib import Path

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Now import and run Celery Beat
from app.core.celery_app import celery_app

if __name__ == "__main__":
    # Run Celery beat scheduler
    celery_app.start(argv=[
        "beat",
        "--loglevel=info",
    ])
