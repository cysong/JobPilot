"""Lifecycle helpers for Celery worker event loop and async engine cleanup."""
from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any

from celery.signals import worker_process_init, worker_process_shutdown

from app.core.database import engine

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_thread_id: int | None = None
_loop_ready = threading.Event()


def _loop_runner() -> None:
    """Run a dedicated asyncio event loop in a daemon thread."""
    global _loop, _loop_thread_id
    loop = asyncio.new_event_loop()
    _loop = loop
    _loop_thread_id = threading.get_ident()
    asyncio.set_event_loop(loop)
    _loop_ready.set()
    try:
        loop.run_forever()
    finally:
        loop.close()


def _ensure_worker_loop() -> asyncio.AbstractEventLoop:
    """Ensure dedicated worker loop thread is started."""
    global _loop_thread
    if _loop is not None and not _loop.is_closed() and _loop.is_running():
        return _loop

    _loop_ready.clear()
    _loop_thread = threading.Thread(
        target=_loop_runner,
        name="celery-asyncio-loop",
        daemon=True,
    )
    _loop_thread.start()
    _loop_ready.wait(timeout=5)

    if _loop is None:
        raise RuntimeError("Failed to initialize Celery asyncio loop")
    return _loop


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return the dedicated background event loop for the worker process."""
    return _ensure_worker_loop()


def run_coroutine_sync(coro: Any) -> Any:
    """
    Submit a coroutine to the dedicated worker loop and block for result.

    This avoids nested run_until_complete() calls under threaded Celery pools.
    """
    loop = _ensure_worker_loop()
    if threading.get_ident() == _loop_thread_id:
        raise RuntimeError("run_coroutine_sync cannot be called from loop thread")

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


@worker_process_init.connect
def _init_worker_process(**kwargs: object) -> None:
    """Create the worker event loop early in the process lifecycle."""
    _ensure_worker_loop()


@worker_process_shutdown.connect
def _shutdown_worker_process(**kwargs: object) -> None:
    """Dispose async engine and close the worker loop on shutdown."""
    global _loop, _loop_thread, _loop_thread_id
    if _loop is None:
        return

    try:
        dispose_future = asyncio.run_coroutine_threadsafe(engine.dispose(), _loop)
        dispose_future.result(timeout=10)
    except (RuntimeError, concurrent.futures.TimeoutError):
        pass
    finally:
        if _loop.is_running():
            _loop.call_soon_threadsafe(_loop.stop)
        if _loop_thread is not None:
            _loop_thread.join(timeout=5)
        _loop = None
        _loop_thread = None
        _loop_thread_id = None
