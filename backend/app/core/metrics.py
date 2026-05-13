"""Prometheus business metrics for JobPilot.

All metrics use the `jobpilot_` prefix and follow Prometheus conventions:
- Durations are in seconds (Grafana renders ms/s/min based on magnitude).
- Label cardinality is bounded by design — no user_id / request_id / UUID labels.
- High-cardinality identifiers (agent_id, task_name) are enumerable in practice.

Registry: uses the default global registry shared with
``prometheus-fastapi-instrumentator``, so these metrics are auto-exposed at the
``/metrics`` endpoint on the API process. Worker-process metrics require a
separate HTTP server (see ``celery_lifecycle``).
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ===== API errors =====

api_error_total = Counter(
    "jobpilot_api_error_total",
    "Application-level API error events emitted from FastAPI exception handlers.",
    labelnames=("endpoint", "code", "exception_type"),
)


# ===== Celery tasks =====

celery_task_total = Counter(
    "jobpilot_celery_task_total",
    "Celery task lifecycle events (success / failure / retry).",
    labelnames=("task_name", "event"),
)

# Task durations span seconds to minutes (LLM polls, ingest, etc.).
celery_task_duration_seconds = Histogram(
    "jobpilot_celery_task_duration_seconds",
    "Celery task execution time in seconds.",
    labelnames=("task_name",),
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600),
)

celery_queue_length = Gauge(
    "jobpilot_celery_queue_length",
    "Current Celery queue length read from Redis broker.",
    labelnames=("queue_name",),
)


# ===== LLM (Agent) calls =====

llm_call_total = Counter(
    "jobpilot_llm_call_total",
    "LLM agent call outcomes.",
    labelnames=("agent_id", "provider", "model", "outcome"),
)

llm_call_duration_seconds = Histogram(
    "jobpilot_llm_call_duration_seconds",
    "LLM agent call latency in seconds.",
    labelnames=("agent_id", "provider", "model"),
    buckets=(0.5, 1, 2.5, 5, 10, 20, 30, 60, 120, 300),
)

llm_tokens_total = Counter(
    "jobpilot_llm_tokens_total",
    "LLM token usage by direction.",
    labelnames=("agent_id", "provider", "model", "kind"),
)


# ===== Resend email =====

resend_email_total = Counter(
    "jobpilot_resend_email_total",
    "Resend email delivery attempts by kind and outcome.",
    labelnames=("kind", "outcome"),
)


# ===== Job ingest =====

job_ingest_total = Counter(
    "jobpilot_job_ingest_total",
    "Manual job URL ingest attempts via /jobs/enqueue.",
    labelnames=("source", "outcome"),
)
