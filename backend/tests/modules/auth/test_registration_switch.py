import httpx
import pytest

from app.core.config import settings
from app.main import app


async def _call(method: str, path: str, **kwargs) -> httpx.Response:
    # ASGITransport skips the lifespan (Redis cache init); neither route needs it.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, "/api/v1/auth" + path, **kwargs)


def _allowed(response: httpx.Response) -> bool:
    body = response.json()
    return (body.get("data") or body)["allowed"]


@pytest.mark.asyncio
async def test_registration_status_reflects_setting(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
    assert _allowed(await _call("GET", "/registration-status")) is False
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", True)
    assert _allowed(await _call("GET", "/registration-status")) is True


@pytest.mark.asyncio
async def test_register_refused_when_closed(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
    response = await _call("POST", "/register", json={
        "email": "new@example.com", "password": "password123", "full_name": "New User"})
    assert response.status_code == 403
    assert response.json()["message"] == "Registration is currently closed"
