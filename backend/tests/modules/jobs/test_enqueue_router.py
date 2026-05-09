"""Surface tests for POST /jobs/enqueue.

We don't have a FastAPI TestClient harness in this project, so:
- A small AST/inspection test asserts the route is registered at the
  expected path and method.
- A direct-call test invokes the router function with an AsyncMock
  service and asserts payload propagation.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.jobs import router as jobs_router_module
from app.modules.jobs.schemas import JobEnqueueRequest, JobEnqueueResponse


def test_enqueue_route_registered():
    paths = {(r.path, tuple(sorted(r.methods))) for r in jobs_router_module.router.routes}  # type: ignore[attr-defined]
    assert ("/jobs/enqueue", ("POST",)) in paths


@pytest.mark.asyncio
async def test_enqueue_router_delegates_to_service():
    fake_resp = JobEnqueueResponse(
        enqueued=False,
        source="seek",
        source_id="1",
        reason="already_in_db",
        existing_job_id=42,
    )
    with patch.object(
        jobs_router_module.service.JobService,
        "enqueue_job_url",
        new=AsyncMock(return_value=fake_resp),
    ) as mocked:
        result = await jobs_router_module.enqueue_job_url(
            payload=JobEnqueueRequest(url="https://www.seek.co.nz/job/1"),
            db=AsyncMock(),
            current_user=AsyncMock(),
        )

    mocked.assert_awaited_once()
    assert result is fake_resp
