# API Response Migration Plan

## Goal

Unify successful and error responses under one envelope:

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

This migration uses a dual-track approach:

- Short term: repair `CustomAPIRoute` so existing success responses are wrapped consistently.
- Long term: require new routes to explicitly use `ApiResponse[T]` and migrate legacy routes gradually.

## Current State

- Error responses are already normalized by global exception handlers.
- Success responses are only partially normalized because many FastAPI route results have already become `JSONResponse` objects before the current `CustomAPIRoute` wrapper inspects them.
- Frontend `apiClient` currently supports both unified envelope payloads and legacy raw payloads.

## Target State

- Standard JSON API responses always use `{code, message, data}`.
- New routes explicitly declare `response_model=ApiResponse[T]`.
- `CustomAPIRoute` remains as a compatibility fallback instead of being the primary contract mechanism.

## Phase 1: Fix `CustomAPIRoute`

Update `backend/app/core/custom_route.py` so that it:

- wraps normal JSON success payloads
- does not double-wrap payloads already shaped like `{code, message, data}`
- passes through:
  - `StreamingResponse`
  - `FileResponse`
  - `RedirectResponse`
  - `204` and `304` responses
  - non-JSON responses

Expected result:

- the majority of legacy success routes immediately return the unified envelope
- frontend payload shape becomes consistent faster without rewriting every router first

## Phase 2: New Route Standard

All newly added routes should:

- use `ApiResponse[T]` as the declared `response_model`
- explicitly return the envelope
- avoid adding fresh dependencies on implicit `CustomAPIRoute` wrapping

Example:

```python
@router.get("/example", response_model=ApiResponse[ExampleResponse])
async def get_example():
    return ApiResponse(
        code=0,
        message="ok",
        data=ExampleResponse(...)
    )
```

## Phase 3: Legacy Route Migration

Recommended module order:

1. `auth`
2. `users`
3. `resumes`
4. `jobs`
5. `applications`
6. `admin`

Rules during migration:

- do not introduce new raw-payload success routes
- keep business code and HTTP status semantically aligned
- keep special responses outside envelope wrapping
- update frontend types and expectations together with backend route migration

## Verification Checklist

For each migration batch:

- verify actual response payload matches documented schema
- verify frontend still unwraps the payload correctly
- add or update backend tests for success envelope shape
- verify file, stream, redirect, and empty responses are not incorrectly wrapped

## End State

When most routes explicitly use `ApiResponse[T]`:

- reduce `CustomAPIRoute` to a safety net only, or
- remove it after confirming no route still depends on implicit wrapping
