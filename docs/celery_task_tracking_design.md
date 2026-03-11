# Celery Task Database Tracking Architecture Design

**Version:** 2.0
**Date:** 2025-01-23
**Status:** Design Proposal

---

## 📋 Executive Summary

This document proposes a new two-tier base class architecture for Celery tasks:

1. **AsyncBaseTask**: Universal async task base class that eliminates boilerplate async wrappers for ALL tasks
2. **DBTrackingTask**: Extends AsyncBaseTask to add automatic workflow status tracking

**Goals:**
1. Replace the current decorator-based approach (`@task_status_guard`) with infrastructure-level base classes
2. Eliminate repetitive async wrapper code in batch/periodic tasks
3. Provide automatic database session management via `self.db`
4. Enable clean async/await syntax in all task definitions

---

## 🎯 Design Objectives

### Primary Goals

1. **Zero Boilerplate Business Code**
   - No manual async wrappers
   - No `@task_status_guard` decorators
   - No manual `workflow_id`/`task_id` propagation

2. **Automatic Status Management**
   - Auto-track: PENDING → RUNNING → SUCCESS/FAILED
   - Auto-record execution time
   - Auto-handle errors and retries

3. **Flexible Configuration**
   - Support first/last task semantics
   - Support single-task and multi-task workflows
   - Compatible with non-tracked batch tasks

4. **Preserve Existing Capabilities**
   - Keep all Celery features (retry, timeout, routing, etc.)
   - Keep async database access
   - Keep error handling logic

---

## 📊 Current System Analysis

### Task Type Classification

Based on codebase analysis, we have **three distinct task patterns**:

#### Type 1: Workflow Task (Requires Tracking)
```python
# Characteristics:
- Uses @task_status_guard(first=True/False, last=True/False)
- Three-layer structure: Celery → Async Bootstrap → Decorated Logic
- Requires workflow/task status management
- Returns structured data: {task_output_data, workflow_output_data}

# Examples:
- analyze_job_async (jobs/tasks.py)
- analyze_resume_async (resumes/tasks.py)
- generate_cover_letter_task (applications/tasks.py)

# Current Structure:
@celery_app.task(bind=True)
def task_name(self, workflow_id, task_id, ...):
    async def _run():
        async for db in get_db():
            return await _execute_xxx(db=db, workflow_id=..., task_id=...)
    return _run_sync(_run())

@task_status_guard(first=True, last=True)
async def _execute_xxx(*, db, workflow_id, task_id, ...):
    # Business logic
    return {"task_output_data": {...}, "workflow_output_data": {...}}
```

#### Type 2: Batch Task (No Tracking)
```python
# Characteristics:
- No @task_status_guard
- No workflow/task records
- Self-contained batch processing
- Returns simple dict or None

# Examples:
- calculate_job_user_matches_task (matching/tasks.py)
- match_user_recent_jobs_task (matching/tasks.py)
- poll_unanalyzed_jobs (jobs/tasks.py)

# Structure:
@celery_app.task(name="...")
def batch_task(param1, param2, ...):
    async def _run():
        async for db in get_db():
            return await _do_batch_work(db, ...)
    return _run_sync(_run())
```

#### Type 3: Periodic Task (No Tracking)
```python
# Characteristics:
- No parameters or fixed parameters
- Scheduled execution
- May trigger other workflow tasks

# Examples:
- run_outbox_consumer (applications/tasks.py)
- poll_unanalyzed_jobs (periodic trigger)

# Structure:
@celery_app.task()
def periodic_task():
    async def _run():
        async with async_session_factory() as db:
            # Work
    asyncio.run(_run())
```

---

## 🔍 Core Requirements

### Requirement 1: Workflow Lifecycle Management

```
State Flow:
PENDING (created)
  ↓ (when first=True)
RUNNING (first task starts)
  ↓
RUNNING (intermediate tasks execute)
  ↓ (when last=True and success)
COMPLETED (last task completes)
  OR
FAILED (any task fails)

Key Points:
- first=True: Mark workflow PENDING → RUNNING
- last=True: Mark workflow RUNNING → COMPLETED
- On failure: Any task failure marks workflow as FAILED
```

### Requirement 2: Task Execution Tracking

```
Each task must record:
- Status: PENDING → RUNNING → SUCCESS/FAILED
- Execution time: execution_time_ms
- Output data: output_data
- Error info: error_message (on failure)
- Celery info: celery_task_id, worker_id
- Retry info: retry_count

Applies to:
- All Type 1 (Workflow Tasks)
- Not needed for Type 2/3 (Batch/Periodic Tasks)
```

### Requirement 3: Structured Output

```python
# Business code returns:
{
  "task_output_data": {...},      # Saved to task_executions.output_data
  "workflow_output_data": {...}   # Saved to workflow_executions.output_data
}

# Key Points:
- task_output_data: Task-level results (e.g., analysis_id)
- workflow_output_data: Workflow-level results (final output)
- When last=True, workflow_output_data is written to workflow
```

### Requirement 4: Error Handling and Retry

```
Failure Handling:
- Catch exception
- Rollback database
- Record error message to task and workflow
- Preserve Celery retry capability

Key Points:
- Base class catches exception → update status → re-raise to Celery
- Celery decides retry based on max_retries
- Final failure state remains FAILED
```

### Requirement 5: Flexibility Requirements

```
Different tasks have different needs:
- Single-step workflow: first=True, last=True
- Multi-step workflow first task: first=True, last=False
- Multi-step workflow middle task: first=False, last=False
- Multi-step workflow last task: first=False, last=True

Key Points:
- Must support configurable first/last behavior
- Cannot be hardcoded in base class
```

---

## 🏗️ Proposed Architecture

### Two-Tier Base Class Hierarchy

```
┌─────────────────────────────────────────────────┐
│         celery.Task (Celery Native)             │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│        AsyncBaseTask (Level 1 - Universal)      │
│  ┌──────────────────────────────────────────┐   │
│  │  Core Capabilities:                      │   │
│  │  • Auto-detect async functions           │   │
│  │  • Auto-create & inject db session       │   │
│  │  • Provide self.db property              │   │
│  │  • Handle sync→async bridging            │   │
│  │  • Automatic session lifecycle           │   │
│  │  • Auto-rollback on error                │   │
│  └──────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  DBTrackingTask  │    │   Business Tasks     │
│  (Level 2)       │    │   (Use AsyncBase)    │
│                  │    │                      │
│  Extends:        │    │  Use Cases:          │
│  • AsyncBaseTask │    │  • Batch tasks       │
│                  │    │  • Periodic tasks    │
│  Adds:           │    │  • Non-tracked jobs  │
│  • before_start  │    │                      │
│  • on_success    │    │  Benefits:           │
│  • on_failure    │    │  • self.db access    │
│  • on_retry      │    │  • No wrappers       │
│  • Workflow mgmt │    │  • Clean async/await │
│  • Status track  │    │                      │
└──────────────────┘    └──────────────────────┘
```

### Architectural Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Business Layer                       │
│         (Pure async business logic, clean code)         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│             Task Base Classes (2 Tiers)                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  AsyncBaseTask (for all async tasks)            │   │
│  │  • Async function wrapping                       │   │
│  │  • Session management                            │   │
│  │  • self.db injection                             │   │
│  │                                                   │   │
│  │  DBTrackingTask (for workflow tasks only)        │   │
│  │  • Inherits AsyncBaseTask capabilities           │   │
│  │  • + Workflow lifecycle hooks                    │   │
│  │  • + Status tracking                             │   │
│  └──────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│               Async DB Session Manager                  │
│   (async_session_factory, connection pooling)          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│            Workflow/Task Repository Layer               │
│        (Database operations, status updates)            │
└─────────────────────────────────────────────────────────┘
```

---

## 🎨 Key Design Decisions

### Decision 0: Two-Tier Base Class Architecture (New)

**Problem:** Current tasks have massive code duplication

```python
# Every task repeats this pattern:
@celery_app.task()
def some_task(params):
    async def _run():                    # ← Boilerplate layer 1
        async for db in get_db():        # ← Boilerplate layer 2
            # Actual business logic
            result = await process(db, params)
            return result
    return _run_sync(_run())             # ← Boilerplate layer 3

# _run_sync repeated in every file:
def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
```

**Solution:** Two-tier base class hierarchy

```python
# Tier 1: AsyncBaseTask - Solves async execution problem
class AsyncBaseTask(Task):
    """
    Universal base for all async tasks.
    Eliminates async wrapper boilerplate.
    """
    abstract = True
    auto_commit = False

    def __call__(self, *args, **kwargs):
        if asyncio.iscoroutinefunction(self.run):
            return self._run_async_task(*args, **kwargs)
        return super().__call__(*args, **kwargs)

    def _run_async_task(self, *args, **kwargs):
        async def _execute():
            async with async_session_factory() as session:
                self._db_session = session
                try:
                    result = await self.run(*args, **kwargs)
                    if self.auto_commit:
                        await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    self._db_session = None
        return asyncio.run(_execute())

    @property
    def db(self) -> AsyncSession:
        if not hasattr(self, '_db_session') or self._db_session is None:
            raise RuntimeError("Database session not available")
        return self._db_session

# Tier 2: DBTrackingTask - Adds workflow tracking
class DBTrackingTask(AsyncBaseTask):
    """
    For workflow tasks requiring status tracking.
    Inherits all AsyncBaseTask capabilities + adds hooks.
    """
    abstract = True

    def __call__(self, *args, **kwargs):
        # Extract workflow metadata
        self._workflow_id = kwargs.get("workflow_id")
        self._task_id = kwargs.get("task_id")
        self._is_first_task = kwargs.get("_is_first_task", False)
        self._is_last_task = kwargs.get("_is_last_task", False)

        if not self._workflow_id or not self._task_id:
            raise ValueError("DBTrackingTask requires workflow_id and task_id")

        self._start_time = time.perf_counter()

        # Call parent (AsyncBaseTask) which handles async execution
        return super().__call__(*args, **kwargs)

    # ... lifecycle hooks (before_start, on_success, on_failure, on_retry)
```

**Usage:**

```python
# Batch tasks: Use AsyncBaseTask
@celery_app.task(base=AsyncBaseTask, bind=True)
async def batch_task(self, params):
    result = await process(self.db, params)
    await self.db.commit()
    return result

# Workflow tasks: Use DBTrackingTask (inherits AsyncBaseTask)
@celery_app.task(base=DBTrackingTask, bind=True)
async def workflow_task(self, business_params):
    result = await process(self.db, business_params)
    await self.db.commit()
    return {
        "task_output_data": {...},
        "workflow_output_data": {...},
    }
```

**Rationale:**
- ✅ **Separation of Concerns**: Async execution (Tier 1) vs Status tracking (Tier 2)
- ✅ **Progressive Enhancement**: Use AsyncBaseTask for simple tasks, DBTrackingTask for workflows
- ✅ **Code Reuse**: DBTrackingTask inherits all AsyncBaseTask capabilities
- ✅ **Zero Boilerplate**: Both tiers eliminate wrapper code
- ✅ **Explicit Opt-in**: Choose appropriate base via `base=` parameter

**Benefits Over Single Base Class:**
- Batch/periodic tasks don't pay the overhead of workflow tracking
- Clear separation between "async execution" and "workflow management"
- AsyncBaseTask can be used independently in other contexts
- Easier to test and maintain (single responsibility principle)

---

### Decision 1: Task Type Distinction (Updated for Two-Tier)

**Approach:** Explicit opt-in via `base` parameter with two choices

```python
# Type 1: Workflow Task (needs tracking)
@celery_app.task(base=DBTrackingTask, bind=True)
async def analyze_job(self, job_id: int):
    # Gets AsyncBaseTask + workflow tracking
    job = await JobRepository.get_by_id(self.db, job_id)
    # ... business logic
    return {
        "task_output_data": {...},
        "workflow_output_data": {...},
    }

# Type 2: Batch/Periodic Task (needs async + db, no tracking)
@celery_app.task(base=AsyncBaseTask, bind=True)
async def batch_processing(self, params):
    # Gets AsyncBaseTask only (no tracking overhead)
    results = await process_batch(self.db, params)
    await self.db.commit()
    return {"processed": len(results)}

# Type 3: Simple sync task (no async, no db, no tracking)
@celery_app.task()
def simple_sync_task(params):
    # Plain Celery task, no base class
    return compute_result(params)
```

**Decision Matrix:**

| Task Type | Base Class | Gets | Use Case |
|-----------|-----------|------|----------|
| **Workflow** | `DBTrackingTask` | Async + DB + Tracking | Job analysis, resume analysis, cover letter generation |
| **Batch/Periodic** | `AsyncBaseTask` | Async + DB | Batch matching, periodic cleanups, data migrations |
| **Simple** | None | Native Celery | Pure computation, external API calls (no DB) |

**Rationale:**
- ✅ **Progressive Enhancement**: Choose the level of infrastructure you need
- ✅ **No Unnecessary Overhead**: Batch tasks don't pay for workflow tracking
- ✅ **Explicit and Clear**: Base class choice documents intent
- ✅ **Backward Compatible**: Existing tasks without `base` still work

### Decision 2: First/Last Configuration

**Approach:** Pass via kwargs from `WorkflowService`

```python
# In WorkflowService.submit_task()
task_kwargs = {
    "workflow_id": workflow_id,
    "task_id": task.id,
    "_is_first_task": True,   # Auto-added by service
    "_is_last_task": True,    # Auto-added by service
}

# In DBTrackingTask
def before_start(self, task_id, args, kwargs):
    is_first = kwargs.get("_is_first_task", False)
    if is_first:
        # Mark workflow as RUNNING
        pass
```

**Rationale:**
- ✅ Simple and direct
- ✅ `WorkflowService` already knows task position
- ✅ No additional database queries
- ✅ Follows "convention over configuration"

**Alternative Considered:**
- ❌ Class attributes: Not flexible enough
- ❌ Database query: Unnecessary overhead
- ❌ Decorator parameters: Celery doesn't support custom params

### Decision 3: Async Database Access in Sync Hooks

**Approach:** Use `asyncio.run()` in Celery hooks

```python
def before_start(self, task_id, args, kwargs):
    # Celery hook is sync, but we need async DB access
    self._run_async(
        self._mark_task_running(workflow_id, task_id, ...)
    )

@staticmethod
def _run_async(coro):
    """Run async coroutine in sync context."""
    return asyncio.run(coro)
```

**Rationale:**
- ✅ Simple and clean
- ✅ Python 3.11+ `asyncio.run()` is efficient
- ✅ Each hook gets fresh event loop (no state pollution)
- ✅ Easy to understand and debug

**Alternative Considered:**
- ❌ Force sync database: Breaks existing architecture
- ❌ Thread-based: Complex and error-prone
- ❌ Reuse event loop: Risk of state pollution

### Decision 4: Async Task Execution

**Challenge:** Celery tasks are sync, but business logic is async

**Approach:** Auto-detect and wrap async functions

```python
class DBTrackingTask(Task):
    def __call__(self, *args, **kwargs):
        # 1. Extract metadata
        # 2. Create db session
        # 3. Detect if task function is async
        # 4. If async, wrap with asyncio.run()
        # 5. Inject db into kwargs

        if asyncio.iscoroutinefunction(self.run):
            # Task is async, wrap it
            result = asyncio.run(self.run(*args, **kwargs))
        else:
            # Task is sync, call directly
            result = self.run(*args, **kwargs)

        return result
```

**Usage:**
```python
@celery_app.task(base=DBTrackingTask, bind=True)
async def analyze_job(self, job_id: int):  # ← Directly define as async
    # self.db automatically available
    job = await JobRepository.get_by_id(self.db, job_id)
    # ... business logic
    return {"task_output_data": {...}, "workflow_output_data": {...}}
```

**Rationale:**
- ✅ Zero boilerplate for business code
- ✅ Natural async/await syntax
- ✅ Automatic session management
- ✅ Clean separation of concerns

### Decision 5: Return Value Structure

**Convention:**
```python
return {
    "task_output_data": {...},      # Task-level results
    "workflow_output_data": {...}   # Workflow-level results
}
```

**Base Class Handling:**
```python
def on_success(self, retval, task_id, args, kwargs):
    if isinstance(retval, dict):
        task_output = retval.get("task_output_data", {})
        workflow_output = retval.get("workflow_output_data", {})
    else:
        # Fallback: wrap non-dict returns
        task_output = {"result": retval}
        workflow_output = {}

    # Save task output
    await TaskRepository.mark_success(task, output_data=task_output)

    # Save workflow output if last task
    is_last = kwargs.get("_is_last_task", False)
    if is_last:
        await WorkflowRepository.mark_completed(workflow, output_data=workflow_output)
```

**Rationale:**
- ✅ Clear separation of task vs workflow outputs
- ✅ Backward compatible (handles non-dict returns)
- ✅ Explicit is better than implicit

---

## 📝 Implementation Overview

### Two-Tier Base Class Structure

#### Level 1: AsyncBaseTask (Foundation)

```python
class AsyncBaseTask(Task):
    """
    Universal base class for all async Celery tasks.

    Provides:
    1. Automatic async function detection and wrapping
    2. Automatic database session creation and injection
    3. Self.db property for clean database access
    4. Automatic session lifecycle management (rollback on error)
    5. Configurable auto-commit behavior

    Usage:
        @celery_app.task(base=AsyncBaseTask, bind=True)
        async def my_async_task(self, param1):
            result = await process(self.db, param1)
            await self.db.commit()
            return result
    """

    abstract = True
    auto_commit = False  # Business code controls commits

    def __call__(self, *args, **kwargs):
        """Intercept call to handle async functions."""
        if asyncio.iscoroutinefunction(self.run):
            return self._run_async_task(*args, **kwargs)
        return super().__call__(*args, **kwargs)

    def _run_async_task(self, *args, **kwargs):
        """Execute async task with session management."""
        async def _execute():
            async with async_session_factory() as session:
                self._db_session = session
                try:
                    result = await self.run(*args, **kwargs)
                    if self.auto_commit:
                        await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    self._db_session = None

        return asyncio.run(_execute())

    @property
    def db(self) -> AsyncSession:
        """Get current database session."""
        if not hasattr(self, '_db_session') or self._db_session is None:
            raise RuntimeError(
                "Database session not available. "
                "Are you accessing self.db outside task execution?"
            )
        return self._db_session
```

#### Level 2: DBTrackingTask (Enhanced)

```python
class DBTrackingTask(AsyncBaseTask):
    """
    Workflow task base class with automatic status tracking.

    Extends: AsyncBaseTask (inherits all async capabilities)

    Adds:
    1. Automatic workflow/task status updates (PENDING→RUNNING→SUCCESS/FAILED)
    2. Execution time tracking
    3. Error recording with traceback
    4. Workflow coordination (first/last task handling)
    5. Celery lifecycle hooks integration

    Usage:
        @celery_app.task(base=DBTrackingTask, bind=True)
        async def analyze_job(self, job_id: int):
            # self.db available from AsyncBaseTask
            # Status tracking automatic
            result = await process(self.db, job_id)
            return {
                "task_output_data": {...},
                "workflow_output_data": {...},
            }
    """

    abstract = True
    auto_commit = False  # Hooks manage commits

    def __call__(self, *args, **kwargs):
        """
        Override AsyncBaseTask to extract workflow metadata.

        Required kwargs (passed by WorkflowService):
        - workflow_id: str
        - task_id: str
        - _is_first_task: bool (optional)
        - _is_last_task: bool (optional)
        """
        self._workflow_id = kwargs.get("workflow_id")
        self._task_id = kwargs.get("task_id")
        self._is_first_task = kwargs.get("_is_first_task", False)
        self._is_last_task = kwargs.get("_is_last_task", False)

        if not self._workflow_id or not self._task_id:
            raise ValueError("DBTrackingTask requires workflow_id and task_id")

        self._start_time = time.perf_counter()

        # Call parent (AsyncBaseTask) which handles async execution
        return super().__call__(*args, **kwargs)

    # ===== Celery Lifecycle Hooks =====

    def before_start(self, task_id, args, kwargs):
        """
        Called when worker picks up task.

        Actions:
        - Mark task as RUNNING
        - Mark workflow as RUNNING (if first task)
        - Record celery_task_id and worker_id
        """
        pass

    def on_success(self, retval, task_id, args, kwargs):
        """
        Called when task completes successfully.

        Actions:
        - Parse return value structure
        - Mark task as SUCCESS with output_data
        - Mark workflow as COMPLETED (if last task)
        - Record execution time
        """
        pass

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails.

        Actions:
        - Extract error message and traceback
        - Mark task as FAILED
        - Mark workflow as FAILED (stop further execution)
        - Record retry count
        """
        pass

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task is retried.

        Actions:
        - Mark task as RETRY
        - Increment retry count
        - Record retry reason
        """
        pass

    # ===== Async Helper =====

    @staticmethod
    def _run_async(coro):
        """Bridge sync hooks to async database operations."""
        return asyncio.run(coro)

    # ===== Database Operations =====

    async def _mark_task_running(self, workflow_id, task_id, ...):
        """Update task and workflow status to RUNNING."""
        async with async_session_factory() as db:
            task = await TaskRepository.get_by_id(db, task_id)
            workflow = await WorkflowRepository.get_by_id(db, workflow_id)

            await TaskRepository.mark_running(db, task, ...)

            # Only mark workflow as RUNNING if this is the first task
            # (determined by _is_first_task in kwargs)
            if is_first_task and workflow.status == WorkflowStatus.PENDING:
                await WorkflowRepository.mark_running(db, workflow, ...)

            await db.commit()

    async def _mark_task_success(self, workflow_id, task_id, ...):
        """Update task status to SUCCESS, optionally complete workflow."""
        async with async_session_factory() as db:
            task = await TaskRepository.get_by_id(db, task_id)
            workflow = await WorkflowRepository.get_by_id(db, workflow_id)

            await TaskRepository.mark_success(db, task, ...)

            # Only mark workflow as COMPLETED if this is the last task
            # (determined by _is_last_task in kwargs)
            if is_last_task:
                await WorkflowRepository.mark_completed(db, workflow, ...)

            await db.commit()

    async def _mark_task_failed(self, workflow_id, task_id, ...):
        """Update task and workflow status to FAILED."""
        async with async_session_factory() as db:
            task = await TaskRepository.get_by_id(db, task_id)
            workflow = await WorkflowRepository.get_by_id(db, workflow_id)

            await TaskRepository.mark_failed(db, task, ...)
            await WorkflowRepository.mark_failed(db, workflow, ...)

            await db.commit()
```

---

## 💡 Usage Examples

### Example 1: Simple Single-Task Workflow

```python
# Before (with decorator):
@celery_app.task(bind=True, max_retries=3)
def analyze_job_async(self, job_id: int, workflow_id: str, task_id: str):
    async def _run():
        async for db in get_db():
            return await _execute_job_analysis(
                db=db, job_id=job_id, workflow_id=workflow_id, task_id=task_id
            )
    return _run_sync(_run())

@task_status_guard(first=True, last=True)
async def _execute_job_analysis(*, db, job_id, workflow_id, task_id):
    job = await JobRepository.get_by_id(db, job_id)
    result = await AgentGateway.get().call(...)
    analysis = await JobAnalysisRepository.upsert(db, job_id, ...)
    await db.commit()

    return {
        "task_output_data": {"analysis_id": analysis.id},
        "workflow_output_data": {"analysis_id": analysis.id},
    }

# After (with DBTrackingTask):
@celery_app.task(base=DBTrackingTask, bind=True, max_retries=3)
async def analyze_job_async(self, job_id: int):
    """Analyze job posting - automatic tracking enabled."""

    job = await JobRepository.get_by_id(self.db, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    result = await AgentGateway.get().call(
        agent_id="job_analyzer",
        input_data=job.content,
    )

    analysis = await JobAnalysisRepository.upsert(
        self.db, job_id=job_id, analysis_data=result.model_dump()
    )
    await self.db.commit()

    return {
        "task_output_data": {"analysis_id": analysis.id},
        "workflow_output_data": {"analysis_id": analysis.id},
    }
```

**Benefits:**
- ✅ No async wrapper boilerplate
- ✅ No `@task_status_guard` decorator
- ✅ No manual `workflow_id`/`task_id` handling
- ✅ `self.db` automatically available
- ✅ Status tracking fully automatic

### Example 2: Multi-Task Workflow

```python
# Task 1: First task in workflow
@celery_app.task(base=DBTrackingTask, bind=True)
async def extract_data(self, source_id: str):
    """Extract data from source - first task."""
    # WorkflowService will pass _is_first_task=True
    # Base class will mark workflow as RUNNING

    data = await DataExtractor.extract(self.db, source_id)

    return {
        "task_output_data": {"records": len(data)},
        "workflow_output_data": {"source_id": source_id},
    }

# Task 2: Middle task in workflow
@celery_app.task(base=DBTrackingTask, bind=True)
async def transform_data(self, data_id: str):
    """Transform extracted data - middle task."""
    # WorkflowService will pass _is_first_task=False, _is_last_task=False
    # Only task status updated, workflow stays RUNNING

    transformed = await DataTransformer.transform(self.db, data_id)

    return {
        "task_output_data": {"transformed_records": len(transformed)},
    }

# Task 3: Last task in workflow
@celery_app.task(base=DBTrackingTask, bind=True)
async def load_data(self, transformed_id: str):
    """Load transformed data - last task."""
    # WorkflowService will pass _is_last_task=True
    # Base class will mark workflow as COMPLETED

    result = await DataLoader.load(self.db, transformed_id)

    return {
        "task_output_data": {"loaded_records": result.count},
        "workflow_output_data": {"final_count": result.count},
    }
```

### Example 3: Batch Task with AsyncBaseTask (New)

```python
# ❌ Old way - nested wrappers and boilerplate
@celery_app.task(name="matching.calculate_matches")
def calculate_job_user_matches(job_analysis_ids: list[int] = None):
    """Batch matching task - no workflow tracking needed."""

    async def _run():
        async for db in get_db():
            analyses = await JobAnalysisRepository.get_by_ids(db, job_analysis_ids)
            total_matches = 0

            for analysis in analyses:
                candidates = await prefilter_candidates(db, analysis)
                for user_id in candidates:
                    user_skills = await UserSkillRepository.get_by_user_id(db, user_id)
                    score = calculate_skill_match_score(user_skills, analysis)
                    if score >= threshold:
                        await UserJobMatchRepository.upsert(db, user_id, analysis.job_id, score)
                        total_matches += 1

            await db.commit()
            return {"jobs": len(analyses), "matches": total_matches}

    return _run_sync(_run())

# ✅ New way - clean and direct with AsyncBaseTask
@celery_app.task(base=AsyncBaseTask, bind=True)
async def calculate_job_user_matches(self, job_analysis_ids: list[int] = None):
    """Batch matching task using AsyncBaseTask for clean async code."""

    analyses = await JobAnalysisRepository.get_by_ids(self.db, job_analysis_ids)
    total_matches = 0

    for analysis in analyses:
        candidates = await prefilter_candidates(self.db, analysis)
        for user_id in candidates:
            user_skills = await UserSkillRepository.get_by_user_id(self.db, user_id)
            score = calculate_skill_match_score(user_skills, analysis)
            if score >= threshold:
                await UserJobMatchRepository.upsert(self.db, user_id, analysis.job_id, score)
                total_matches += 1

    await self.db.commit()
    return {"jobs": len(analyses), "matches": total_matches}
```

**Benefits of AsyncBaseTask for Batch Tasks:**
- ✅ Eliminates `async def _run()` wrapper
- ✅ Eliminates `async for db in get_db()`
- ✅ Eliminates `_run_sync(_run())` call
- ✅ Provides `self.db` automatically
- ✅ Auto-rollback on error
- ✅ No workflow tracking overhead (vs DBTrackingTask)
- ✅ 2 levels of indentation removed

### Example 4: Periodic Task with AsyncBaseTask (New)

```python
# ❌ Old way
@celery_app.task()
def run_outbox_consumer():
    """Periodic task to process outbox events."""

    async def _run():
        async with async_session_factory() as db:
            batch_size = app_module_settings.OUTBOX_BATCH_SIZE
            await process_outbox_batch(db, batch_size=batch_size)

    asyncio.run(_run())

# ✅ New way
@celery_app.task(base=AsyncBaseTask, bind=True)
async def run_outbox_consumer(self):
    """Periodic task using AsyncBaseTask."""

    batch_size = app_module_settings.OUTBOX_BATCH_SIZE
    await process_outbox_batch(self.db, batch_size=batch_size)
    await self.db.commit()
```

**Note:** AsyncBaseTask is perfect for batch/periodic tasks that need async+db but not workflow tracking.

---

## 🔄 Workflow Recovery and Retry

When a workflow with multiple chained tasks fails, we need mechanisms to recover and retry. This section describes two recovery strategies supported by the DBTrackingTask architecture.

### Recovery Strategies Overview

| Strategy | Use Case | Advantages | Disadvantages |
|----------|----------|------------|---------------|
| **Retry from Failed Task** | Most common scenario, transient errors (API timeout, rate limit) | Fast, reuses successful results, cost-effective | Assumes previous results still valid |
| **Reset All and Retry** | Data corruption, logic errors, schema changes | Clean state, no stale data issues | Repeats all work, higher cost |

### Strategy 1: Retry from Failed Task

**Scenario:** A 5-task workflow fails on Task 3 due to a transient error (API timeout, rate limit). Tasks 1-2 succeeded and produced valid results.

**Goal:** Resume from Task 3 without re-running Tasks 1-2.

```python
from app.modules.workflow.service import WorkflowService
from app.modules.workflow.repository import WorkflowRepository, TaskRepository
from app.shared.enums import TaskStatus, WorkflowStatus
from celery import chain

class WorkflowRecoveryService:
    """Service for recovering and retrying failed workflows."""

    @staticmethod
    async def retry_from_failed_task(
        db: AsyncSession,
        workflow_id: str,
    ) -> dict:
        """
        Retry workflow starting from the first failed task.

        Steps:
        1. Find the first failed task
        2. Reset only that task and subsequent tasks to PENDING
        3. Rebuild Celery chain from the failed task onwards
        4. Submit the chain

        Args:
            db: Database session
            workflow_id: Workflow to retry

        Returns:
            Status dictionary with retry information
        """
        # 1. Load workflow and tasks
        workflow = await WorkflowRepository.get_by_id(db, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        if workflow.status not in [WorkflowStatus.FAILED, WorkflowStatus.PARTIAL]:
            raise ValueError(f"Workflow {workflow_id} is not in failed state (current: {workflow.status})")

        tasks = await TaskRepository.get_by_workflow_id(db, workflow_id)
        tasks_sorted = sorted(tasks, key=lambda t: t.created_at)

        # 2. Find first failed task
        first_failed_idx = None
        for idx, task in enumerate(tasks_sorted):
            if task.status == TaskStatus.FAILED:
                first_failed_idx = idx
                break

        if first_failed_idx is None:
            raise ValueError(f"No failed tasks found in workflow {workflow_id}")

        # 3. Reset failed task and all subsequent tasks to PENDING
        tasks_to_retry = tasks_sorted[first_failed_idx:]
        for task in tasks_to_retry:
            await TaskRepository.reset_for_retry(db, task.id)

        # 4. Reset workflow status to PENDING
        await WorkflowRepository.update_status(
            db,
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            error_message=None,
        )
        await db.commit()

        # 5. Rebuild Celery chain from failed task
        celery_tasks = []
        for idx, task in enumerate(tasks_to_retry):
            is_first = (idx == 0)  # First in retry chain
            is_last = (idx == len(tasks_to_retry) - 1)  # Last in retry chain

            # Get Celery task callable
            celery_task = WorkflowService._get_celery_task_for_type(task.task_type)

            # Prepare kwargs (merge original input_data with workflow metadata)
            task_kwargs = {
                **task.input_data,
                "workflow_id": workflow_id,
                "task_id": task.id,
                "_is_first_task": is_first,
                "_is_last_task": is_last,
            }

            celery_tasks.append(celery_task.s(**task_kwargs))

        # 6. Submit chain
        retry_chain = chain(*celery_tasks)
        retry_chain.apply_async()

        return {
            "status": "retry_submitted",
            "workflow_id": workflow_id,
            "retry_from_task": tasks_to_retry[0].id,
            "tasks_to_retry": len(tasks_to_retry),
            "tasks_reused": first_failed_idx,
        }
```

**Usage Example:**

```python
# API Endpoint for retry
@router.post("/workflows/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed workflow from the first failed task."""
    result = await WorkflowRecoveryService.retry_from_failed_task(
        db=db,
        workflow_id=workflow_id,
    )
    return result
```

**Output Example:**

```json
{
  "status": "retry_submitted",
  "workflow_id": "wf-123",
  "retry_from_task": "task-3",
  "tasks_to_retry": 3,
  "tasks_reused": 2
}
```

### Strategy 2: Reset All and Retry

**Scenario:** A workflow failed due to data corruption or a logic error that invalidates previous results. Need to start fresh from the beginning.

**Goal:** Reset entire workflow and all tasks to PENDING, then re-run from Task 1.

```python
class WorkflowRecoveryService:
    """Service for recovering and retrying failed workflows."""

    @staticmethod
    async def reset_all_and_retry(
        db: AsyncSession,
        workflow_id: str,
    ) -> dict:
        """
        Reset entire workflow and retry from the beginning.

        Steps:
        1. Reset ALL tasks to PENDING (including successful ones)
        2. Reset workflow to PENDING
        3. Rebuild entire Celery chain
        4. Submit the chain

        Args:
            db: Database session
            workflow_id: Workflow to reset and retry

        Returns:
            Status dictionary with reset information
        """
        # 1. Load workflow and tasks
        workflow = await WorkflowRepository.get_by_id(db, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        tasks = await TaskRepository.get_by_workflow_id(db, workflow_id)
        tasks_sorted = sorted(tasks, key=lambda t: t.created_at)

        # 2. Reset ALL tasks to PENDING
        for task in tasks_sorted:
            await TaskRepository.reset_for_retry(db, task.id)

        # 3. Reset workflow to PENDING
        await WorkflowRepository.reset_for_retry(db, workflow_id)
        await db.commit()

        # 4. Rebuild entire Celery chain
        celery_tasks = []
        for idx, task in enumerate(tasks_sorted):
            is_first = (idx == 0)
            is_last = (idx == len(tasks_sorted) - 1)

            celery_task = WorkflowService._get_celery_task_for_type(task.task_type)

            task_kwargs = {
                **task.input_data,
                "workflow_id": workflow_id,
                "task_id": task.id,
                "_is_first_task": is_first,
                "_is_last_task": is_last,
            }

            celery_tasks.append(celery_task.s(**task_kwargs))

        # 5. Submit chain
        full_chain = chain(*celery_tasks)
        full_chain.apply_async()

        return {
            "status": "reset_and_retry_submitted",
            "workflow_id": workflow_id,
            "tasks_reset": len(tasks_sorted),
            "retry_from": "beginning",
        }
```

**Usage Example:**

```python
# API Endpoint for reset and retry
@router.post("/workflows/{workflow_id}/reset-retry")
async def reset_and_retry_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Reset entire workflow and retry from the beginning."""
    result = await WorkflowRecoveryService.reset_all_and_retry(
        db=db,
        workflow_id=workflow_id,
    )
    return result
```

**Output Example:**

```json
{
  "status": "reset_and_retry_submitted",
  "workflow_id": "wf-123",
  "tasks_reset": 5,
  "retry_from": "beginning"
}
```

### Recovery Strategy Decision Tree

```
Failed Workflow
    ├─ Transient Error? (API timeout, rate limit, network)
    │   └─ YES → Retry from Failed Task
    │       ├─ Fast recovery
    │       ├─ Reuses successful results
    │       └─ Cost-effective
    │
    ├─ Data Corruption? (Invalid intermediate results)
    │   └─ YES → Reset All and Retry
    │       ├─ Clean state guaranteed
    │       └─ No stale data issues
    │
    ├─ Logic Error? (Bug in task code)
    │   └─ Fix code first, then:
    │       ├─ If fix affects previous tasks → Reset All and Retry
    │       └─ If fix only affects failed task → Retry from Failed Task
    │
    └─ Schema Change? (Database migration, API change)
        └─ YES → Reset All and Retry
            └─ Ensures all data conforms to new schema
```

### Implementation Requirements

**1. WorkflowService Enhancement**

Add helper method to get Celery task callable from task type:

```python
class WorkflowService:
    @staticmethod
    def _get_celery_task_for_type(task_type: TaskType) -> Task:
        """Map TaskType enum to Celery task callable."""
        from app.modules.jobs.tasks import analyze_job_async
        from app.modules.resumes.tasks import analyze_resume_async
        from app.modules.applications.tasks import generate_cover_letter_task

        task_map = {
            TaskType.JOB_ANALYSIS: analyze_job_async,
            TaskType.RESUME_ANALYSIS: analyze_resume_async,
            TaskType.COVER_LETTER_GENERATION: generate_cover_letter_task,
        }

        if task_type not in task_map:
            raise ValueError(f"Unknown task type: {task_type}")

        return task_map[task_type]
```

**2. Repository Methods (Already Implemented)**

The following methods already exist in `backend/app/modules/workflow/repositories.py`:

- `TaskRepository.reset_for_retry(db, task_id)` - Lines 154-163
- `WorkflowRepository.reset_for_retry(db, workflow_id)` - Lines 96-102

These methods reset status to PENDING and clear error messages.

**3. API Endpoints**

Add to `backend/app/modules/workflow/router.py`:

```python
@router.post("/workflows/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retry workflow from first failed task."""
    result = await WorkflowRecoveryService.retry_from_failed_task(db, workflow_id)
    return result

@router.post("/workflows/{workflow_id}/reset-retry")
async def reset_and_retry_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Reset entire workflow and retry from beginning."""
    result = await WorkflowRecoveryService.reset_all_and_retry(db, workflow_id)
    return result
```

### Error Handling in Recovery

```python
class WorkflowRecoveryService:
    @staticmethod
    async def retry_from_failed_task(db: AsyncSession, workflow_id: str) -> dict:
        try:
            # Validation checks
            workflow = await WorkflowRepository.get_by_id(db, workflow_id)

            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            if workflow.status not in [WorkflowStatus.FAILED, WorkflowStatus.PARTIAL]:
                raise ValueError(
                    f"Cannot retry workflow in status {workflow.status}. "
                    f"Only FAILED or PARTIAL workflows can be retried."
                )

            # Check for active retries
            tasks = await TaskRepository.get_by_workflow_id(db, workflow_id)
            if any(t.status == TaskStatus.RUNNING for t in tasks):
                raise ValueError(
                    f"Workflow {workflow_id} has tasks currently running. "
                    f"Wait for them to finish before retrying."
                )

            # Proceed with retry logic...

        except Exception as exc:
            logger.error(f"Failed to retry workflow {workflow_id}: {exc}")
            raise
```

### Monitoring Retry Success

Track retry statistics in workflow metadata:

```python
# In WorkflowExecution model, add retry tracking fields:
retry_count: int = 0
last_retry_at: Optional[datetime] = None
retry_history: list[dict] = []  # JSON field

# Update on retry:
await WorkflowRepository.record_retry(
    db=db,
    workflow_id=workflow_id,
    retry_type="from_failed_task",  # or "reset_all"
    retry_from_task_id=task_id,
)
```

---

## 🔄 Migration Strategy

### Phase 1: Coexistence (Low Risk)

```
Timeline: Sprint 1-2
Goal: Introduce base class without breaking existing code

Actions:
1. Implement DBTrackingTask base class
2. Keep @task_status_guard decorator
3. Migrate 1-2 simple tasks as proof of concept
4. Monitor behavior in development

Risk: Low - both approaches work independently
```

### Phase 2: Gradual Migration (Medium Risk)

```
Timeline: Sprint 3-5
Goal: Migrate majority of workflow tasks

Actions:
1. Migrate all single-task workflows
2. Migrate simple multi-task workflows
3. Update WorkflowService to pass _is_first/_is_last
4. Keep complex workflows on decorator temporarily

Risk: Medium - need careful testing of multi-task workflows
```

### Phase 3: Complete Replacement (High Risk)

```
Timeline: Sprint 6+
Goal: Remove decorator completely

Actions:
1. Migrate remaining complex workflows
2. Remove @task_status_guard decorator
3. Clean up legacy async wrapper code
4. Update documentation

Risk: High - affects all workflow tasks
```

### Migration Checklist per Task

```markdown
- [ ] Identify task type (workflow/batch/periodic)
- [ ] If batch/periodic: Skip migration
- [ ] If workflow task:
  - [ ] Add `base=DBTrackingTask` to @celery_app.task()
  - [ ] Change task function to `async def`
  - [ ] Replace `db` parameter with `self.db`
  - [ ] Remove async wrapper (_run, _run_sync)
  - [ ] Remove @task_status_guard decorator
  - [ ] Remove workflow_id/task_id from function signature
  - [ ] Test task execution
  - [ ] Verify status updates in database
  - [ ] Test error handling and retry
```

---

## ⚠️ Considerations and Limitations

### 1. Event Loop Management

**Challenge:** Celery hooks are sync, but we need async DB access

**Solution:**
- Use `asyncio.run()` in hooks (creates fresh loop each time)
- Acceptable overhead for long-running tasks
- Clean and simple implementation

**Monitoring:**
- Track hook execution time
- Alert if hook takes >100ms

### 2. Database Connection Pool

**Current Config:**
```python
pool_size=10
max_overflow=20
# Max 30 concurrent connections
```

**Impact:**
- Each hook creates a new session
- 3 hooks per task (before_start, on_success/on_failure, on_retry)
- High task concurrency might exhaust pool

**Mitigation:**
- Hooks are fast (<50ms typically)
- Connections are short-lived
- If needed, increase pool_size or add connection timeout

### 3. Error Handling in Hooks

**Philosophy:** Hooks should never fail task execution

```python
def before_start(self, task_id, args, kwargs):
    try:
        self._run_async(self._mark_task_running(...))
    except Exception as exc:
        # Log error but don't raise
        logger.warning("Failed to update task status", exc_info=True)
        # Task execution continues
```

**Rationale:**
- Status tracking is observability, not business logic
- Database errors shouldn't block task execution
- Task can still succeed even if tracking fails

### 4. Return Value Convention

**Required Structure:**
```python
{
    "task_output_data": {...},
    "workflow_output_data": {...}
}
```

**Enforcement:**
- Not enforced at runtime (to support incremental adoption)
- Base class handles both dict and non-dict returns
- Best practice: always return structured dict

### 5. Async Function Detection

**Implementation:**
```python
if asyncio.iscoroutinefunction(self.run):
    # Wrap async function
    result = asyncio.run(self.run(*args, **kwargs))
```

**Edge Cases:**
- Handles both async def and sync def
- Supports existing sync tasks
- Backward compatible

---

## 🎯 Success Criteria

### Technical Metrics

```
✅ Zero boilerplate in business code
   - No async wrappers
   - No decorator required
   - No manual parameter passing

✅ Complete lifecycle tracking
   - All status transitions recorded
   - Execution time captured
   - Error messages logged

✅ Backward compatibility
   - Existing @task_status_guard tasks still work
   - Batch tasks unaffected
   - Gradual migration possible

✅ Performance acceptable
   - Hook overhead <50ms per task
   - No connection pool exhaustion
   - No event loop conflicts
```

### Business Metrics

```
✅ Developer productivity
   - Faster task development
   - Fewer bugs in status management
   - Easier debugging

✅ System observability
   - Complete task execution history
   - Clear error traces
   - Workflow state always accurate

✅ Maintenance cost
   - Centralized status management logic
   - Easier to extend and modify
   - Less code duplication
```

---

## 📚 Comprehensive Comparison

### Table 1: Current vs Proposed Architecture

| Aspect | Current (Decorator) | Proposed (Two-Tier Base) |
|--------|---------------------|--------------------------|
| **Workflow Tasks** | @task_status_guard + wrappers | DBTrackingTask only |
| **Batch Tasks** | Manual async wrappers | AsyncBaseTask only |
| **Boilerplate Lines** | 8-10 lines per task | 0 lines |
| **Nesting Levels** | 3-4 levels | 0 levels |
| **_run_sync Function** | Duplicated in every file | Encapsulated in base class |
| **DB Access** | `db` parameter | `self.db` property |
| **Status Management** | Manual decorator | Automatic (DBTrackingTask) |
| **Session Lifecycle** | Manual (async for) | Automatic |
| **Error Rollback** | Manual try/except | Automatic |

### Table 2: Feature Matrix by Base Class

| Feature | No Base | AsyncBaseTask | DBTrackingTask |
|---------|---------|---------------|----------------|
| **Async/Await Support** | ❌ Manual | ✅ Automatic | ✅ Inherited |
| **self.db Property** | ❌ | ✅ | ✅ Inherited |
| **Session Management** | ❌ | ✅ | ✅ Inherited |
| **Auto Rollback** | ❌ | ✅ | ✅ Inherited |
| **Workflow Tracking** | ❌ | ❌ | ✅ |
| **Status Hooks** | ❌ | ❌ | ✅ |
| **Execution Timing** | ❌ | ❌ | ✅ |
| **Error Recording** | ❌ | ❌ | ✅ |

### Table 3: When to Use Which Base Class

| Scenario | Use | Reason |
|----------|-----|--------|
| Job analysis, resume analysis | `DBTrackingTask` | Needs workflow tracking |
| Cover letter generation | `DBTrackingTask` | Multi-step workflow |
| Batch matching jobs | `AsyncBaseTask` | Async+DB, no tracking needed |
| Periodic cleanup tasks | `AsyncBaseTask` | Async+DB, no tracking needed |
| Outbox consumer | `AsyncBaseTask` | Async+DB, no tracking needed |
| Pure calculation (no DB) | No base | Keep it simple |
| External API call (no DB) | No base | No database needed |

### Table 4: Code Reduction Metrics

| Task Type | Old Lines | New Lines | Reduction |
|-----------|-----------|-----------|-----------|
| **Workflow Task** | 25-30 | 10-15 | 50-60% |
| **Batch Task** | 20-25 | 8-12 | 50-60% |
| **Periodic Task** | 15-20 | 6-10 | 50-60% |

**Additional Benefits:**
- No more `_run_sync` duplication (saves ~10 lines per file)
- No more `async for db in get_db()` pattern
- Consistent error handling across all tasks
- Centralized session management

---

## 🚀 Next Steps

### Immediate Actions

1. **Implement Two-Tier Base Classes**
   - Create `backend/app/core/celery_task_base.py`
   - Implement `AsyncBaseTask` (Level 1)
     - Async function detection
     - Session management
     - self.db property
   - Implement `DBTrackingTask` (Level 2)
     - Inherit from AsyncBaseTask
     - Add lifecycle hooks
     - Add workflow tracking logic
   - Add comprehensive logging
   - Write unit tests for both classes

2. **Update WorkflowService**
   - Add `_is_first_task` and `_is_last_task` to kwargs
   - Detect task position in workflow
   - Update submit_task() method

3. **Proof of Concept - Phase 1 (AsyncBaseTask)**
   - Migrate 2-3 batch tasks to AsyncBaseTask
     - calculate_job_user_matches_task
     - match_user_recent_jobs_task
     - run_outbox_consumer
   - Verify self.db works correctly
   - Measure code reduction
   - Test error handling (rollback)

4. **Proof of Concept - Phase 2 (DBTrackingTask)**
   - Migrate 1-2 simple workflow tasks
     - analyze_job_async
     - analyze_resume_async
   - Verify status tracking works
   - Test first/last task semantics
   - Measure performance overhead

5. **Documentation**
   - Update developer guide with two-tier architecture
   - Add migration guide (separate for AsyncBaseTask and DBTrackingTask)
   - Document decision tree (which base class to use)
   - Create troubleshooting guide
   - Add code examples for each pattern

### Future Enhancements

1. **Enhanced Observability**
   - Metrics collection (execution time, success rate)
   - Structured logging with correlation IDs
   - Dashboard for workflow visualization

2. **Advanced Features**
   - Task dependency graph enforcement
   - Automatic retry strategy per task type
   - Circuit breaker for failing tasks
   - Dead letter queue for failed workflows

3. **Performance Optimization**
   - Connection pooling tuning
   - Batch status updates for high-volume tasks
   - Async signal handling (non-blocking hooks)

---

## 📖 References

### Internal Documentation
- [Architecture Design](./architecture.md)
- [Workflow Design](./workflow-design.md)
- [Development Progress](./progress.md)

### External Resources
- [Celery Task Inheritance](https://docs.celeryq.dev/en/stable/userguide/tasks.html#custom-task-classes)
- [Celery Signals and Events](https://docs.celeryq.dev/en/stable/userguide/signals.html)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)

---

**Document Status:** Draft for Review
**Next Review Date:** TBD
**Owner:** Backend Team
