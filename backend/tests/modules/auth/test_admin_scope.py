"""require_admin_scope: admin sessions pass; admin API keys pass only with the scope."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import ForbiddenError
from app.modules.admin.dependencies import require_admin_scope
from app.modules.auth.schemas import ApiKeyCreate
from app.shared.enums import Role

dep = require_admin_scope("matching:labels")


def _user(role, method, scopes=None):
    return SimpleNamespace(role=role, _auth_method=method, _api_key_scopes=scopes)


@pytest.mark.asyncio
async def test_admin_session_passes():
    user = _user(Role.ADMIN, "jwt")
    assert await dep(user) is user


@pytest.mark.asyncio
async def test_admin_api_key_needs_the_scope():
    assert await dep(_user(Role.ADMIN, "api_key", ["matching:labels"]))
    with pytest.raises(ForbiddenError):
        await dep(_user(Role.ADMIN, "api_key", []))


@pytest.mark.asyncio
async def test_non_admin_is_rejected_even_with_scope():
    with pytest.raises(ForbiddenError):
        await dep(_user(Role.USER, "api_key", ["matching:labels"]))
    with pytest.raises(ForbiddenError):
        await dep(_user(Role.USER, "jwt"))


def test_api_key_create_validates_scopes():
    assert ApiKeyCreate(name="k", scopes=["matching:labels", "matching:labels"]).scopes == ["matching:labels"]
    assert ApiKeyCreate(name="k").scopes == []
    with pytest.raises(ValueError):
        ApiKeyCreate(name="k", scopes=["admin:all"])
