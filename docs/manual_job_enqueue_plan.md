# Manual Job Enqueue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Job-listing-page button that lets any logged-in user submit a job URL to an external AWS Function URL, which scrapes and inserts into `seek_jobs`.

**Architecture:** Frontend dialog → backend `/jobs/enqueue` endpoint → backend proxies POST to AWS Function URL with `X-API-Key` header → backend resolves `existing_job_id` for `already_in_db` cases → frontend renders status (stays open, link to existing job).

**Tech Stack:** FastAPI + httpx (backend), React + TanStack Query + shadcn/ui Dialog (frontend), Pydantic, pytest with `httpx.MockTransport` for upstream stubbing.

---

## Task 1: Add `ServiceUnavailableError` exception

**Files:**
- Modify: `backend/app/core/exceptions.py`
- Test: `backend/tests/core/test_exceptions.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/core/__init__.py` (empty) if not present, then `backend/tests/core/test_exceptions.py`:

```python
from fastapi import status

from app.core.exceptions import ServiceUnavailableError
from app.core.response_codes import ResponseCode


def test_service_unavailable_error_defaults():
    err = ServiceUnavailableError()
    assert err.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert err.response_code == ResponseCode.INTERNAL_ERROR
    assert err.message == "Service unavailable"


def test_service_unavailable_error_custom_message():
    err = ServiceUnavailableError("upstream down")
    assert err.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert err.message == "upstream down"
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && pytest tests/core/test_exceptions.py -v
```
Expected: FAIL with `ImportError: cannot import name 'ServiceUnavailableError'`.

- [ ] **Step 3: Implement the exception**

Append to `backend/app/core/exceptions.py`:

```python
class ServiceUnavailableError(JobPilotException):
    """Upstream / dependency unavailable (HTTP 503)."""

    def __init__(self, message: str = "Service unavailable"):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            response_code=ResponseCode.INTERNAL_ERROR,
        )
```

- [ ] **Step 4: Run test to verify it passes**

```
cd backend && pytest tests/core/test_exceptions.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```
git add backend/app/core/exceptions.py backend/tests/core/__init__.py backend/tests/core/test_exceptions.py
git commit -m "feat(core): add ServiceUnavailableError (503) exception"
```

---

## Task 2: Add `ENQUEUE_API_URL` / `ENQUEUE_API_KEY` settings

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add settings**

In `backend/app/core/config.py`, add these two fields inside the `Settings` class (group with the other "Job Analysis" / external integration settings):

```python
    # External job enqueue API (AWS Function URL).
    # Empty string disables the manual-enqueue endpoint (returns 503).
    ENQUEUE_API_URL: str = ""
    ENQUEUE_API_KEY: str = ""
```

- [ ] **Step 2: Sanity-check import**

```
cd backend && python -c "from app.core.config import settings; print(settings.ENQUEUE_API_URL, settings.ENQUEUE_API_KEY)"
```
Expected: prints two empty strings (or whatever is in `.env`).

- [ ] **Step 3: Commit**

```
git add backend/app/core/config.py
git commit -m "feat(config): add ENQUEUE_API_URL and ENQUEUE_API_KEY settings"
```

---

## Task 3: Add repository helper `get_by_source_and_source_id`

**Files:**
- Modify: `backend/app/modules/jobs/repository.py`
- Test: `backend/tests/modules/jobs/test_repository_get_by_source.py`

- [ ] **Step 1: Write the failing test (AST-style, mirrors project convention)**

Create `backend/tests/modules/jobs/test_repository_get_by_source.py`:

```python
"""Surface contract for JobRepository.get_by_source_and_source_id.

The router/service layer relies on this method to resolve an internal
job_id from (source, source_id) when the AWS enqueue API reports
already_in_db. The signature must remain stable.
"""
from __future__ import annotations

import inspect

from app.modules.jobs.repository import JobRepository


def test_get_by_source_and_source_id_signature():
    fn = JobRepository.get_by_source_and_source_id
    sig = inspect.signature(fn)
    params = list(sig.parameters)
    # First arg is `db` (AsyncSession), then source, then source_id.
    assert params == ["db", "source", "source_id"], params
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && pytest tests/modules/jobs/test_repository_get_by_source.py -v
```
Expected: FAIL with `AttributeError: type object 'JobRepository' has no attribute 'get_by_source_and_source_id'`.

- [ ] **Step 3: Implement the helper**

In `backend/app/modules/jobs/repository.py`, inside `class JobRepository`, add (place near `get_by_id`):

```python
    @staticmethod
    async def get_by_source_and_source_id(
        db: AsyncSession,
        source: str,
        source_id: str,
    ) -> Optional[SeekJob]:
        """Resolve a SeekJob by its (source, source_id) unique pair.

        Used by the manual-enqueue flow to fill `existing_job_id` when the
        AWS enqueue API reports `already_in_db`. Hits the
        `uq_seek_jobs_source_source_id` unique index.
        """
        result = await db.execute(
            select(SeekJob).where(
                SeekJob.source == source,
                SeekJob.source_id == source_id,
            )
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Run test to verify it passes**

```
cd backend && pytest tests/modules/jobs/test_repository_get_by_source.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/modules/jobs/repository.py backend/tests/modules/jobs/test_repository_get_by_source.py
git commit -m "feat(jobs): add JobRepository.get_by_source_and_source_id helper"
```

---

## Task 4: Add `JobEnqueueRequest` / `JobEnqueueResponse` schemas

**Files:**
- Modify: `backend/app/modules/jobs/schemas.py`

- [ ] **Step 1: Add schemas**

Append to `backend/app/modules/jobs/schemas.py`:

```python
class JobEnqueueRequest(BaseModel):
    """Body for POST /jobs/enqueue — single URL to push to AWS scraper."""

    url: str = Field(..., description="Job listing URL")


class JobEnqueueResponse(BaseModel):
    """Result of a manual enqueue attempt.

    `existing_job_id` is populated only when the upstream API reports
    `already_in_db` AND we successfully resolve the matching SeekJob
    by (source, source_id).
    """

    enqueued: bool
    source: Optional[str] = None
    source_id: Optional[str] = None
    reason: Optional[str] = None
    existing_job_id: Optional[int] = None
```

(`Field` and `Optional` are already imported at the top of the file; verify the imports include `from pydantic import BaseModel, Field` and `from typing import Optional`.)

- [ ] **Step 2: Sanity-check imports**

```
cd backend && python -c "from app.modules.jobs.schemas import JobEnqueueRequest, JobEnqueueResponse; r = JobEnqueueResponse(enqueued=True, source='seek', source_id='1'); print(r.model_dump())"
```
Expected: `{'enqueued': True, 'source': 'seek', 'source_id': '1', 'reason': None, 'existing_job_id': None}`

- [ ] **Step 3: Commit**

```
git add backend/app/modules/jobs/schemas.py
git commit -m "feat(jobs): add JobEnqueueRequest/Response schemas"
```

---

## Task 5: Implement `JobService.enqueue_job_url`

**Files:**
- Modify: `backend/app/modules/jobs/service.py`
- Test: `backend/tests/modules/jobs/test_enqueue_service.py`

This task uses `httpx.MockTransport` to stub the AWS Function URL. Keep tests pure-async, no DB except the optional `already_in_db` lookup (which we patch out via a fake repository call — see step 1 below; we DO NOT spin up a real DB session for service tests).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/modules/jobs/test_enqueue_service.py`:

```python
"""Unit tests for JobService.enqueue_job_url.

The service is the only layer that calls the AWS Function URL. We stub
the URL with httpx.MockTransport (no network). The (source, source_id)
-> existing_job_id lookup is patched on JobRepository, so these tests
need no real DB.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import BadRequestError, ServiceUnavailableError
from app.modules.jobs import service as job_service_module
from app.modules.jobs.service import JobService


_AWS_URL = "https://aws.example/enqueue"
_AWS_KEY = "secret-key"


def _client_factory(handler):
    """Return an async-context-manager that yields an httpx.AsyncClient
    using MockTransport(handler). Patched into the service for testing.
    """

    class _Cm:
        def __init__(self, *args, **kwargs):
            self._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        async def __aenter__(self):
            return self._client

        async def __aexit__(self, *exc):
            await self._client.aclose()

    return _Cm


def _patch_settings(monkeypatch, url=_AWS_URL, key=_AWS_KEY):
    monkeypatch.setattr(job_service_module.settings, "ENQUEUE_API_URL", url)
    monkeypatch.setattr(job_service_module.settings, "ENQUEUE_API_KEY", key)


def _make_response(status_code: int, body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status_code, json=body)


@pytest.mark.asyncio
async def test_enqueue_returns_enqueued_true(monkeypatch):
    _patch_settings(monkeypatch)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return _make_response(200, {"enqueued": True, "source": "seek", "source_id": "82345678"})

    monkeypatch.setattr(job_service_module.httpx, "AsyncClient", _client_factory(handler))

    result = await JobService.enqueue_job_url(db=AsyncMock(), url="https://www.seek.co.nz/job/82345678")

    assert result.enqueued is True
    assert result.source == "seek"
    assert result.source_id == "82345678"
    assert result.reason is None
    assert result.existing_job_id is None
    assert captured["url"] == _AWS_URL
    assert captured["headers"]["x-api-key"] == _AWS_KEY
    assert captured["body"] == {"url": "https://www.seek.co.nz/job/82345678"}


@pytest.mark.asyncio
async def test_enqueue_already_in_db_resolves_existing_job_id(monkeypatch):
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(
            200,
            {"enqueued": False, "reason": "already_in_db", "source": "seek", "source_id": "42"},
        )

    monkeypatch.setattr(job_service_module.httpx, "AsyncClient", _client_factory(handler))

    fake_job = type("J", (), {"id": 999})()
    with patch.object(
        job_service_module.JobRepository,
        "get_by_source_and_source_id",
        new=AsyncMock(return_value=fake_job),
    ) as mocked:
        result = await JobService.enqueue_job_url(db=AsyncMock(), url="https://www.seek.co.nz/job/42")

    mocked.assert_awaited_once()
    args, kwargs = mocked.await_args
    # signature is (db, source, source_id)
    assert args[1] == "seek" and args[2] == "42"
    assert result.enqueued is False
    assert result.reason == "already_in_db"
    assert result.existing_job_id == 999


@pytest.mark.asyncio
async def test_enqueue_already_in_db_existing_id_none_when_missing(monkeypatch):
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(
            200,
            {"enqueued": False, "reason": "already_in_db", "source": "seek", "source_id": "X"},
        )

    monkeypatch.setattr(job_service_module.httpx, "AsyncClient", _client_factory(handler))

    with patch.object(
        job_service_module.JobRepository,
        "get_by_source_and_source_id",
        new=AsyncMock(return_value=None),
    ):
        result = await JobService.enqueue_job_url(db=AsyncMock(), url="https://www.seek.co.nz/job/X")

    assert result.enqueued is False
    assert result.reason == "already_in_db"
    assert result.existing_job_id is None


@pytest.mark.asyncio
async def test_enqueue_aws_400_passes_through_error_text(monkeypatch):
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(400, {"error": "unrecognized url", "supported": ["seek"]})

    monkeypatch.setattr(job_service_module.httpx, "AsyncClient", _client_factory(handler))

    with pytest.raises(BadRequestError) as exc_info:
        await JobService.enqueue_job_url(db=AsyncMock(), url="https://example.com/x")

    assert "unrecognized url" in exc_info.value.message


@pytest.mark.asyncio
async def test_enqueue_aws_401_raises_service_unavailable(monkeypatch):
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(401, {"error": "unauthorized"})

    monkeypatch.setattr(job_service_module.httpx, "AsyncClient", _client_factory(handler))

    with pytest.raises(ServiceUnavailableError):
        await JobService.enqueue_job_url(db=AsyncMock(), url="https://www.seek.co.nz/job/1")


@pytest.mark.asyncio
async def test_enqueue_aws_500_raises_service_unavailable(monkeypatch):
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return _make_response(500, {"error": "internal", "request_id": "abc"})

    monkeypatch.setattr(job_service_module.httpx, "AsyncClient", _client_factory(handler))

    with pytest.raises(ServiceUnavailableError):
        await JobService.enqueue_job_url(db=AsyncMock(), url="https://www.seek.co.nz/job/1")


@pytest.mark.asyncio
async def test_enqueue_network_error_raises_service_unavailable(monkeypatch):
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(job_service_module.httpx, "AsyncClient", _client_factory(handler))

    with pytest.raises(ServiceUnavailableError):
        await JobService.enqueue_job_url(db=AsyncMock(), url="https://www.seek.co.nz/job/1")


@pytest.mark.asyncio
async def test_enqueue_missing_config_raises_service_unavailable(monkeypatch):
    _patch_settings(monkeypatch, url="", key="")

    with pytest.raises(ServiceUnavailableError):
        await JobService.enqueue_job_url(db=AsyncMock(), url="https://www.seek.co.nz/job/1")
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && pytest tests/modules/jobs/test_enqueue_service.py -v
```
Expected: All tests FAIL with `AttributeError: type object 'JobService' has no attribute 'enqueue_job_url'` (and an import error on `httpx` if it's not yet imported in `service.py`).

- [ ] **Step 3: Implement the service method**

In `backend/app/modules/jobs/service.py`:

1. At the top of the file, after the existing imports, add:

```python
import httpx
import logging

from app.core.config import settings
from app.core.exceptions import BadRequestError, ServiceUnavailableError
from app.modules.jobs.schemas import JobEnqueueResponse


logger = logging.getLogger(__name__)
```

(If `BadRequestError` is already imported elsewhere, merge into the existing line. Same for `settings`.)

2. Inside `class JobService`, add (e.g. at the bottom of the class):

```python
    @staticmethod
    async def enqueue_job_url(db: AsyncSession, url: str) -> JobEnqueueResponse:
        """Forward `url` to the AWS Function URL and shape the response.

        Mapping (see docs/manual_job_enqueue_design.md):
        - 200 enqueued=true               -> return as-is
        - 200 enqueued=false already_in_db -> resolve existing_job_id
        - 400 (any AWS error)             -> BadRequestError(error_text)
        - 401 / 500 / network / timeout   -> ServiceUnavailableError
        - missing config                  -> ServiceUnavailableError
        """
        api_url = settings.ENQUEUE_API_URL
        api_key = settings.ENQUEUE_API_KEY
        if not api_url or not api_key:
            logger.warning("ENQUEUE_API_URL/KEY not configured")
            raise ServiceUnavailableError("Manual enqueue is not configured")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    api_url,
                    headers={
                        "X-API-Key": api_key,
                        "Content-Type": "application/json",
                    },
                    json={"url": url},
                )
        except httpx.HTTPError as exc:
            logger.warning("Enqueue API network error: %s", exc)
            raise ServiceUnavailableError("Enqueue service unavailable") from exc

        # Try to parse JSON; tolerate empty/non-JSON 5xx responses.
        try:
            body = resp.json()
        except ValueError:
            body = {}

        if resp.status_code == 200:
            enqueued = bool(body.get("enqueued"))
            source = body.get("source")
            source_id = body.get("source_id")
            reason = body.get("reason")
            existing_job_id: int | None = None

            if not enqueued and reason == "already_in_db" and source and source_id:
                existing = await JobRepository.get_by_source_and_source_id(
                    db, source, source_id
                )
                if existing is not None:
                    existing_job_id = existing.id

            return JobEnqueueResponse(
                enqueued=enqueued,
                source=source,
                source_id=source_id,
                reason=reason,
                existing_job_id=existing_job_id,
            )

        if resp.status_code == 400:
            error_text = str(body.get("error") or "Bad request")
            raise BadRequestError(error_text)

        # 401, 500, anything else: hide upstream specifics.
        request_id = body.get("request_id")
        logger.warning(
            "Enqueue API non-200: status=%s body=%s request_id=%s",
            resp.status_code,
            body,
            request_id,
        )
        raise ServiceUnavailableError("Enqueue service unavailable")
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && pytest tests/modules/jobs/test_enqueue_service.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```
git add backend/app/modules/jobs/service.py backend/tests/modules/jobs/test_enqueue_service.py
git commit -m "feat(jobs): add JobService.enqueue_job_url (AWS Function URL proxy)"
```

---

## Task 6: Wire `POST /jobs/enqueue` router endpoint

**Files:**
- Modify: `backend/app/modules/jobs/router.py`
- Test: `backend/tests/modules/jobs/test_enqueue_router.py`

We don't have an existing FastAPI client integration harness in this project (other tests are AST-style or pure-unit). To stay consistent, this task uses an AST-style guard test that asserts the router exposes `enqueue_job_url` with the right decorator, plus a pure-unit test that calls the function directly with mocked dependencies.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/modules/jobs/test_enqueue_router.py`:

```python
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
    assert ("/enqueue", ("POST",)) in paths


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
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && pytest tests/modules/jobs/test_enqueue_router.py -v
```
Expected: FAIL — route not registered, function does not exist.

- [ ] **Step 3: Add the endpoint**

In `backend/app/modules/jobs/router.py`:

1. Extend the imports from `app.modules.jobs.schemas` to include `JobEnqueueRequest` and `JobEnqueueResponse` (add to the existing import block):

```python
from app.modules.jobs.schemas import (
    # ... existing entries ...
    JobEnqueueRequest,
    JobEnqueueResponse,
)
```

2. Add the route. Place it near the other POST routes (e.g. after `mark_job_viewed`, before `save_job`) so it doesn't conflict with the `/{job_id}` matcher:

```python
@router.post("/enqueue", response_model=JobEnqueueResponse)
async def enqueue_job_url(
    payload: JobEnqueueRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Manually submit a job URL to the external AWS scraper.

    Any logged-in user may call this. The actual scrape happens
    asynchronously on AWS; this endpoint only reports enqueue status.
    """
    return await service.JobService.enqueue_job_url(db, payload.url)
```

**Important:** because the router has a `GET /{job_id}` and `POST /{job_id}/...` matchers, `/enqueue` MUST be declared **before** the `/{job_id}` routes for FastAPI to resolve it correctly. In the current router, all `/{job_id}` routes come after the static ones (`/saved`, `/filters`, `/sources/meta`); place `/enqueue` next to those.

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && pytest tests/modules/jobs/test_enqueue_router.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Run the full jobs test module to catch regressions**

```
cd backend && pytest tests/modules/jobs -v
```
Expected: all tests pass (existing AST guards still hold).

- [ ] **Step 6: Commit**

```
git add backend/app/modules/jobs/router.py backend/tests/modules/jobs/test_enqueue_router.py
git commit -m "feat(jobs): add POST /jobs/enqueue endpoint"
```

---

## Task 7: Frontend types + API client method

**Files:**
- Modify: `frontend/src/types/job.ts`
- Modify: `frontend/src/api/jobs.ts`

- [ ] **Step 1: Add types**

Append to `frontend/src/types/job.ts`:

```typescript
export interface EnqueueJobRequest {
  url: string
}

export interface EnqueueJobResponse {
  enqueued: boolean
  source?: string | null
  source_id?: string | null
  reason?: string | null
  existing_job_id?: number | null
}
```

- [ ] **Step 2: Add API method**

In `frontend/src/api/jobs.ts`:

1. Extend the type imports:

```typescript
import type {
  // ... existing entries ...
  EnqueueJobResponse,
} from '@/types/job'
```

2. Add a method to the `jobsApi` object (near the existing mutation-style methods like `markJobViewed`):

```typescript
  /**
   * Manually submit a job URL to the AWS scraper. Any logged-in user
   * can call this — backend holds the X-API-Key.
   */
  enqueueJobUrl: async (url: string): Promise<EnqueueJobResponse> => {
    const result = await apiClient.post<EnqueueJobResponse, EnqueueJobResponse>(
      '/jobs/enqueue',
      { url },
    )
    return result
  },
```

- [ ] **Step 3: Type-check**

```
cd frontend && pnpm tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/types/job.ts frontend/src/api/jobs.ts
git commit -m "feat(jobs/api): add enqueueJobUrl client + types"
```

---

## Task 8: Build `EnqueueJobDialog` component

**Files:**
- Create: `frontend/src/features/jobs/components/EnqueueJobDialog.tsx`

This component owns the dialog UX: URL input, submit, in-memory result history (last 5), explicit close.

- [ ] **Step 1: Implement the component**

Create `frontend/src/features/jobs/components/EnqueueJobDialog.tsx`:

```tsx
import { useState } from "react"
import { Link } from "react-router-dom"
import { CheckCircle2, Info, AlertCircle, Loader2 } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { jobsApi } from "@/api/jobs"
import { ApiError } from "@/types/api"
import type { EnqueueJobResponse } from "@/types/job"

type ResultEntry =
  | {
      kind: "enqueued"
      source?: string | null
      source_id?: string | null
    }
  | {
      kind: "exists"
      source?: string | null
      source_id?: string | null
      existing_job_id?: number | null
    }
  | {
      kind: "bad_request"
      message: string
    }
  | {
      kind: "unavailable"
    }

interface EnqueueJobDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const URL_REGEX = /^https?:\/\/.+/i
const MAX_RESULTS = 5

export function EnqueueJobDialog({ open, onOpenChange }: EnqueueJobDialogProps) {
  const [url, setUrl] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<ResultEntry[]>([])

  const isValid = URL_REGEX.test(url.trim())
  const canSubmit = !submitting && isValid

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return

    setSubmitting(true)
    try {
      const data: EnqueueJobResponse = await jobsApi.enqueueJobUrl(url.trim())
      const entry: ResultEntry =
        data.enqueued
          ? {
              kind: "enqueued",
              source: data.source,
              source_id: data.source_id,
            }
          : data.reason === "already_in_db"
            ? {
                kind: "exists",
                source: data.source,
                source_id: data.source_id,
                existing_job_id: data.existing_job_id ?? null,
              }
            : {
                // Unknown 200 shape — show as exists-like info row
                kind: "exists",
                source: data.source,
                source_id: data.source_id,
                existing_job_id: null,
              }
      setResults((prev) => [entry, ...prev].slice(0, MAX_RESULTS))
      setUrl("")
    } catch (err) {
      const entry: ResultEntry =
        err instanceof ApiError && err.httpStatus === 400
          ? { kind: "bad_request", message: err.message }
          : { kind: "unavailable" }
      setResults((prev) => [entry, ...prev].slice(0, MAX_RESULTS))
      // Keep `url` in the input on error so user can edit & retry.
    } finally {
      setSubmitting(false)
    }
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setUrl("")
      setResults([])
    }
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Job by URL</DialogTitle>
          <DialogDescription>
            手动提交一个岗位 URL，系统会调用爬虫将其加入队列。
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <Input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.seek.co.nz/job/82345678"
            disabled={submitting}
            autoFocus
          />
          <div className="flex justify-end">
            <Button type="submit" disabled={!canSubmit}>
              {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Submit
            </Button>
          </div>
        </form>

        {results.length > 0 && (
          <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
            {results.map((r, i) => (
              <ResultRow key={i} entry={r} />
            ))}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ResultRow({ entry }: { entry: ResultEntry }) {
  switch (entry.kind) {
    case "enqueued":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">
          <CheckCircle2 className="h-4 w-4" />
          <span>
            已加入抓取队列{" "}
            <span className="font-mono text-xs">
              {entry.source}/{entry.source_id}
            </span>
          </span>
        </div>
      )
    case "exists":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sky-800">
          <Info className="h-4 w-4" />
          <span>
            已存在{" "}
            <span className="font-mono text-xs">
              {entry.source}/{entry.source_id}
            </span>
          </span>
          {entry.existing_job_id != null && (
            <Link
              to={`/jobs/${entry.existing_job_id}`}
              className="ml-auto text-indigo-600 underline"
            >
              查看岗位
            </Link>
          )}
        </div>
      )
    case "bad_request":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">
          <AlertCircle className="h-4 w-4" />
          <span>{entry.message}</span>
        </div>
      )
    case "unavailable":
      return (
        <div className="flex items-center gap-2 text-sm rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">
          <AlertCircle className="h-4 w-4" />
          <span>服务暂不可用，请稍后再试</span>
        </div>
      )
  }
}
```

**Notes for the engineer:**
- `ApiError` from `@/types/api` exposes `httpStatus` and `message` — already used elsewhere in the codebase. The 400 branch surfaces the upstream error text passed through by the backend (`unrecognized url`, etc.).
- `react-router-dom` `Link` is the existing router (used across the app for `/jobs/<id>`). If you import it for the first time in this folder, follow whatever `JobCard.tsx` does (likely `react-router-dom`).

- [ ] **Step 2: Verify the imports resolve**

If `Input` isn't yet exported from `@/components/ui/input`, check:

```
cd frontend && find src/components/ui -name 'input*'
```
It should list `input.tsx`. If it doesn't exist, run `pnpm dlx shadcn-ui@latest add input` (the project already uses shadcn — `Input` will follow the same pattern as `Button`).

- [ ] **Step 3: Type-check**

```
cd frontend && pnpm tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/features/jobs/components/EnqueueJobDialog.tsx
git commit -m "feat(jobs/ui): add EnqueueJobDialog for manual URL submission"
```

---

## Task 9: Wire button into `JobListingPage`

**Files:**
- Modify: `frontend/src/features/jobs/JobListingPage.tsx`

The button must be visible in all three view modes. In `all` view it lives in the search-row (after `Filters`). In `recommended` / `saved` views, the search-row is absent, so we put the button on the same row as the Tabs, right-aligned.

- [ ] **Step 1: Modify the page**

In `frontend/src/features/jobs/JobListingPage.tsx`:

1. Add imports at the top:

```tsx
import { useState } from "react"
import { Plus } from "lucide-react"
import { EnqueueJobDialog } from "@/features/jobs/components/EnqueueJobDialog"
```

(Merge `useState` into the existing `react` import; `useEffect` and `useMemo` are already there.)

2. Inside `JobListingPage()`, add state for the dialog (top of the function, near the other hooks):

```tsx
const [enqueueOpen, setEnqueueOpen] = useState(false)
```

3. Modify the Tabs row to include the button on the right (replace the existing `<Tabs value={viewMode} onValueChange={handleViewChange}>...</Tabs>` block):

```tsx
<div className="flex items-center justify-between gap-4">
  <Tabs value={viewMode} onValueChange={handleViewChange}>
    <TabsList className="grid w-full max-w-lg grid-cols-3">
      <TabsTrigger value="recommended" className="gap-2">
        <Sparkles className="h-4 w-4" />
        Recommended
      </TabsTrigger>
      <TabsTrigger value="all" className="gap-2">
        <Briefcase className="h-4 w-4" />
        All Jobs
      </TabsTrigger>
      <TabsTrigger value="saved" className="gap-2">
        <Star className="h-4 w-4" />
        Saved
      </TabsTrigger>
    </TabsList>
  </Tabs>
  <Button
    variant="outline"
    className="gap-2"
    onClick={() => setEnqueueOpen(true)}
  >
    <Plus className="h-4 w-4" />
    <span className="hidden sm:inline">Add Job by URL</span>
  </Button>
</div>
```

(Replaces only the wrapping `<div className="">` around the Tabs. The button now sits flush-right of the Tabs in all three view modes.)

4. At the end of the JSX (just before the outer `</div>` that closes `<div className="flex flex-col h-full">`), mount the dialog:

```tsx
<EnqueueJobDialog open={enqueueOpen} onOpenChange={setEnqueueOpen} />
```

- [ ] **Step 2: Type-check**

```
cd frontend && pnpm tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Manual smoke test (dev server)**

```
cd frontend && pnpm dev
```

In the browser:
- Navigate to `/jobs`. Verify the "Add Job by URL" button is visible across Recommended / All Jobs / Saved tabs.
- Click it → dialog opens, input focused.
- Without setting `ENQUEUE_API_URL` in backend env, submit → red "服务暂不可用" row appears, dialog stays open.
- Type non-URL → submit button disabled.
- Close dialog → results cleared.

(End-to-end with a real AWS Function URL only after backend env is configured; not required for the commit.)

- [ ] **Step 4: Commit**

```
git add frontend/src/features/jobs/JobListingPage.tsx
git commit -m "feat(jobs/ui): wire Add Job by URL button into JobListingPage"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run full backend test suite**

```
cd backend && pytest -q
```
Expected: all tests pass.

- [ ] **Step 2: Run frontend type-check + build**

```
cd frontend && pnpm tsc --noEmit && pnpm build
```
Expected: build succeeds.

- [ ] **Step 3: Document env vars**

Add to `backend/.env.example` (or wherever existing settings are documented; if no `.env.example` exists, skip):

```
ENQUEUE_API_URL=
ENQUEUE_API_KEY=
```

- [ ] **Step 4: Final commit (if any new docs/env changes)**

```
git add backend/.env.example
git commit -m "docs: document ENQUEUE_API_URL/KEY env vars"
```

(Skip if no file was changed.)

---

## Self-Review Notes

- **Spec coverage:**
  - Backend config (Task 2), exception (Task 1), repository (Task 3), schemas (Task 4), service with full mapping table (Task 5), router (Task 6) — all covered.
  - Frontend types/client (Task 7), dialog with stay-open + 5-result history + already-in-db link (Task 8), button placement across all three views (Task 9).
  - 503 mapping for missing config / 401 / 500 / network — covered in Task 5 tests.
  - "已存在" navigation when `existing_job_id` is null is handled (link omitted) — covered in Task 5 test.
- **No placeholders** — every code block is concrete.
- **Type consistency** — `EnqueueJobResponse` fields in TS match the backend schema in Task 4; `enqueueJobUrl` signature matches usage in Task 8.
