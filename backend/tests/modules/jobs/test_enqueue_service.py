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
    # Capture the real AsyncClient before monkeypatch replaces it on the
    # httpx module — otherwise the patched name would recursively resolve
    # back to _Cm itself.
    real_async_client = httpx.AsyncClient

    class _Cm:
        def __init__(self, *args, **kwargs):
            self._client = real_async_client(transport=httpx.MockTransport(handler))

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
