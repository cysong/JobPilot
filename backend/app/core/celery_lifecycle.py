"""Lifecycle helpers for Celery worker event loop and async engine cleanup."""
from __future__ import annotations

import asyncio
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.database import engine

_loop: asyncio.AbstractEventLoop | None = None


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return a long-lived event loop for the Celery worker process."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


@worker_process_init.connect
def _init_worker_process(**kwargs: object) -> None:
    """Create the worker event loop early in the process lifecycle."""
    get_worker_loop()


@worker_process_shutdown.connect
def _shutdown_worker_process(**kwargs: object) -> None:
    """Dispose async engine and close the worker loop on shutdown."""
    global _loop
    if _loop is None:
        return
    try:
        _loop.run_until_complete(engine.dispose())
    finally:
        _loop.close()
        _loop = None
