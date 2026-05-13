"""Celery worker startup script with automatic path configuration."""
import argparse
import os
import sys
from pathlib import Path

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Configure logging before Celery initializes its own loggers
from app.core.logging_config import configure_logging

configure_logging("celery_worker")

# Now import and run Celery
from app.core.celery_app import celery_app
from app.core import celery_lifecycle  # noqa: F401  # Register worker-only signal handlers (metrics HTTP server, async loop)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start JobPilot Celery worker")
    parser.add_argument(
        "--loglevel", default=os.getenv("CELERY_LOGLEVEL", "info"))
    parser.add_argument(
        "--pool",
        default=os.getenv("CELERY_WORKER_POOL", "solo"),
        help="Celery pool type, e.g. threads/solo/prefork/eventlet/gevent",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("CELERY_WORKER_CONCURRENCY",
                    str(max(2, min(8, os.cpu_count() or 4))))),
        help="Number of worker threads/processes",
    )
    parser.add_argument(
        "--queues",
        default=os.getenv("CELERY_WORKER_QUEUES", ""),
        help="Comma-separated queue names to consume",
    )
    parser.add_argument(
        "--prefetch-multiplier",
        type=int,
        default=int(os.getenv("CELERY_PREFETCH_MULTIPLIER", "1")),
        help="Messages to prefetch per worker slot",
    )
    parser.add_argument(
        "--max-tasks-per-child",
        type=int,
        default=int(os.getenv("CELERY_MAX_TASKS_PER_CHILD", "0")),
        help="Restart child worker after N tasks (pool dependent)",
    )
    parser.add_argument(
        "--without-gossip",
        action="store_true",
        default=os.getenv("CELERY_WITHOUT_GOSSIP", "false").lower() == "true",
        help="Disable worker gossip",
    )
    parser.add_argument(
        "--without-mingle",
        action="store_true",
        default=os.getenv("CELERY_WITHOUT_MINGLE", "false").lower() == "true",
        help="Disable worker mingle",
    )
    parser.add_argument(
        "--without-heartbeat",
        action="store_true",
        default=os.getenv("CELERY_WITHOUT_HEARTBEAT",
                          "false").lower() == "true",
        help="Disable worker heartbeat",
    )
    parser.add_argument(
        "--hostname",
        default=os.getenv("CELERY_WORKER_HOSTNAME", ""),
        help="Custom worker hostname",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    worker_argv = [
        "worker",
        f"--loglevel={args.loglevel}",
        f"--pool={args.pool}",
        f"--concurrency={args.concurrency}",
        f"--prefetch-multiplier={args.prefetch_multiplier}",
    ]

    if args.queues:
        worker_argv.append(f"--queues={args.queues}")
    if args.max_tasks_per_child > 0:
        worker_argv.append(f"--max-tasks-per-child={args.max_tasks_per_child}")
    if args.without_gossip:
        worker_argv.append("--without-gossip")
    if args.without_mingle:
        worker_argv.append("--without-mingle")
    if args.without_heartbeat:
        worker_argv.append("--without-heartbeat")
    if args.hostname:
        worker_argv.append(f"--hostname={args.hostname}")

    celery_app.worker_main(argv=worker_argv)
