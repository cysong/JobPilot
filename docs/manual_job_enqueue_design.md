# Manual Job Enqueue Design

Date: 2026-05-09
Status: Draft (awaiting implementation)

## Background

The crawler periodically populates `seek_jobs` from external sources, but in
some cases jobs may be missed (link-only ads, source rotation, transient
failures). Operators (and any logged-in user) need a way to manually feed a
single job URL to the crawler pipeline so the listing can be picked up.

An AWS Function URL (the "enqueue API") already exists. It accepts a job URL,
recognizes the source, and enqueues the URL for downstream scraping that
writes into `seek_jobs`.

## Goals

- One-click "补漏" path on the Job listing page for any logged-in user.
- Send the URL to the AWS Function URL, surface a clear status, and link to
  the existing job when the URL is already in DB.

## Non-goals

- Batch submission (single URL only — YAGNI).
- Persistent history of manual submissions (session-only display in dialog).
- Per-user rate limiting (rely on AWS-side controls).
- Webhook / push notification when scraping finishes.
- Admin-only gating (open to all logged-in users).

## External contract (AWS Function URL)

```
POST <ENQUEUE_API_URL>
Headers:
  X-API-Key: <secret>
  Content-Type: application/json
Body:
  {"url": "<job url>"}
```

Responses:

| Status | Body |
|---|---|
| 200 | `{"enqueued": true, "source": "seek", "source_id": "82345678"}` |
| 200 | `{"enqueued": false, "reason": "already_in_db", "source": "seek", "source_id": "82345678"}` |
| 400 | `{"error": "missing 'url'"}` |
| 400 | `{"error": "invalid json body"}` |
| 400 | `{"error": "unrecognized url", "supported": [...]}` |
| 401 | `{"error": "unauthorized"}` |
| 500 | `{"error": "internal", "request_id": "a1b2c3d4"}` |

## Architecture

```
[Frontend dialog] -- POST /api/v1/jobs/enqueue { url } --> [Backend]
                                                              |
                                            POST <ENQUEUE_API_URL> (X-API-Key)
                                                              |
                                                    [AWS Function URL]
                                                              |
                            <----- { enqueued, source, source_id, reason? } ----
[Backend]
  - if reason == "already_in_db": resolve internal job_id by (source, source_id)
  - return { enqueued, source, source_id, reason, existing_job_id }
[Frontend]
  - render result row in dialog (keep dialog open)
  - already_in_db -> link to /jobs/<existing_job_id>
```

The API key never leaves the backend.

## Backend

### Configuration

`backend/app/core/config.py`:

- `ENQUEUE_API_URL: str = ""`
- `ENQUEUE_API_KEY: str = ""`

If either is empty at request time, the endpoint returns `503` with a
"service not configured" message; the frontend renders a generic
"服务暂不可用" notice.

### Exceptions

`backend/app/core/exceptions.py` — add a new exception class:

```python
class ServiceUnavailableError(JobPilotException):
    def __init__(self, message: str = "Service unavailable"):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            response_code=ResponseCode.INTERNAL_ERROR,
        )
```

(Reused for: missing config, AWS 401/500, network/timeout failures.)

### Schemas

`backend/app/modules/jobs/schemas.py`:

```python
class JobEnqueueRequest(BaseModel):
    url: HttpUrl

class JobEnqueueResponse(BaseModel):
    enqueued: bool
    source: str | None = None
    source_id: str | None = None
    reason: str | None = None
    existing_job_id: int | None = None
```

### Repository

`backend/app/modules/jobs/repository.py`:

- `JobRepository.get_by_source_and_source_id(db, source, source_id) -> SeekJob | None`
  - Single query against the existing `(source, source_id)` unique index.

### Service

`backend/app/modules/jobs/service.py`:

- `JobService.enqueue_job_url(db, url: str) -> JobEnqueueResponse`
  - Validate `settings.ENQUEUE_API_URL` and `settings.ENQUEUE_API_KEY`; raise
    `ServiceUnavailableError` if either is empty.
  - Use `httpx.AsyncClient(timeout=10)` to POST `{"url": url}` with the
    `X-API-Key` header.
  - Map results:
    - AWS 200 enqueued=true → return as-is.
    - AWS 200 enqueued=false reason=already_in_db → look up internal
      `job.id` via repository; populate `existing_job_id`.
    - AWS 400 → wrap into `BadRequestError`, passing through the AWS
      `error` text (so the user sees "unrecognized url", etc.).
    - AWS 401 / 500, network error, timeout → log with the AWS
      `request_id` if available, raise `ServiceUnavailableError`.

### Router

`backend/app/modules/jobs/router.py`:

```python
@router.post("/enqueue", response_model=JobEnqueueResponse)
async def enqueue_job_url(
    payload: JobEnqueueRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.JobService.enqueue_job_url(db, str(payload.url))
```

Auth: standard `get_current_user` (any logged-in user).

## Frontend

### API client

`frontend/src/api/jobs.ts`:

- `jobsApi.enqueueJobUrl(url: string): Promise<EnqueueJobResponse>`

### Types

`frontend/src/types/job.ts`:

- `EnqueueJobRequest { url: string }`
- `EnqueueJobResponse { enqueued: boolean; source?: string; source_id?: string; reason?: string; existing_job_id?: number }`

### New component

`frontend/src/features/jobs/components/EnqueueJobDialog.tsx`:

- shadcn `Dialog` + `Input` + `Button`.
- Local state:
  - `url: string` (controlled input)
  - `submitting: boolean`
  - `results: ResultEntry[]` (last 5, in-memory only, cleared on close)
- Behavior:
  - Submit button disabled when `submitting` or URL fails simple
    `^https?://` regex.
  - On submit: POST → push result to `results`, clear input on success
    (any 2xx), keep input on validation error so user can edit.
  - Dialog stays open until user closes it explicitly.
- Result row rendering:
  - `enqueued=true` → green check + "已加入抓取队列  source/source_id"
  - `enqueued=false, reason="already_in_db"` → info icon + "已存在  source/source_id" + `<Link>查看岗位</Link>` to `/jobs/<existing_job_id>`
  - 400 (BadRequestError) → red icon + raw error text
  - 503 / network → red icon + "服务暂不可用，请稍后再试"

### List page wiring

`frontend/src/features/jobs/JobListingPage.tsx`:

- Add an `Add Job by URL` button (lucide `Plus` icon) in the header card,
  visible across all three view modes (recommended / all / saved).
- Placement:
  - In `all` view: same control row, right after `Filters` toggle.
  - In `recommended` / `saved` views: aligned to the right end of the
    Tabs row (no other controls there today).
- Clicking opens `EnqueueJobDialog`.
- After a successful enqueue (`enqueued=true`), do NOT auto-refresh the
  list — the job will only appear once the downstream scraper writes it.

## Error / status mapping

| AWS response | Backend response | Frontend display |
|---|---|---|
| 200 enqueued=true | 200 | "✅ 已加入抓取队列" |
| 200 enqueued=false reason=already_in_db | 200 + `existing_job_id` | "ℹ️ 已存在 → [查看岗位]" |
| 400 (any AWS error) | 400 (`BadRequestError`, error text passed through) | red banner with the error text |
| 401 unauthorized | 503 | "服务暂不可用" + backend logs the upstream 401 |
| 500 internal (with `request_id`) | 503 | "服务暂不可用" + backend logs `request_id` |
| network / timeout | 503 | "服务暂不可用" |

The 401 case is treated as a misconfiguration on our side, not surfaced
verbatim to the user.

## Testing

Backend (`tests/modules/jobs/test_enqueue.py`):

- Use `httpx.MockTransport` to stub the AWS function URL.
- Cover all five mapped cases above + timeout.
- For `already_in_db`: pre-seed a `SeekJob(source="seek", source_id="X")`
  and assert `existing_job_id` is populated correctly; also assert it is
  `None` when no matching row exists (defensive — should not normally
  happen but the AWS source-of-truth is independent of our DB).
- Settings missing → assert 503.

Frontend: no automated tests; manual verification against:

- New URL → enqueued=true result row.
- Same URL twice → already_in_db with working "查看岗位" link.
- Garbage URL → 400 error banner.
- Backend down / config missing → 503 banner.

## Risk

- AWS Function URL latency: the user-facing call is synchronous up to the
  AWS response. 10 s timeout caps the worst case.
- API key rotation: handled by env redeploy; no DB migration needed.
- Abuse: any logged-in user can call. Acceptable given small user base;
  AWS side controls cost. Revisit if abuse appears.
