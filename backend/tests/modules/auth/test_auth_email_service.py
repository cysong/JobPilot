import sys
import types

import pytest

from app.modules.auth.email_service import AuthEmailService


@pytest.mark.asyncio
async def test_send_includes_reply_to_when_configured(monkeypatch):
    sent_payloads = []
    fake_resend = types.SimpleNamespace(
        api_key=None,
        Emails=types.SimpleNamespace(send=lambda payload: sent_payloads.append(payload)),
    )

    monkeypatch.setitem(sys.modules, "resend", fake_resend)
    monkeypatch.setattr("app.modules.auth.email_service.settings.RESEND_API_KEY", "test-api-key")
    monkeypatch.setattr(
        "app.modules.auth.email_service.settings.RESEND_FROM_EMAIL",
        "noreply@mail.freeclaw.cloud",
    )
    monkeypatch.setattr(
        "app.modules.auth.email_service.settings.RESEND_REPLY_TO_EMAIL",
        "owner@gmail.com",
    )

    await AuthEmailService._send(
        to_email="user@example.com",
        subject="Subject",
        html="<p>Hello</p>",
        kind="verification",
    )

    assert fake_resend.api_key == "test-api-key"
    assert sent_payloads == [
        {
            "from": "noreply@mail.freeclaw.cloud",
            "to": ["user@example.com"],
            "subject": "Subject",
            "html": "<p>Hello</p>",
            "reply_to": "owner@gmail.com",
        }
    ]


@pytest.mark.asyncio
async def test_send_omits_reply_to_when_not_configured(monkeypatch):
    sent_payloads = []
    fake_resend = types.SimpleNamespace(
        api_key=None,
        Emails=types.SimpleNamespace(send=lambda payload: sent_payloads.append(payload)),
    )

    monkeypatch.setitem(sys.modules, "resend", fake_resend)
    monkeypatch.setattr("app.modules.auth.email_service.settings.RESEND_API_KEY", "test-api-key")
    monkeypatch.setattr(
        "app.modules.auth.email_service.settings.RESEND_FROM_EMAIL",
        "noreply@mail.freeclaw.cloud",
    )
    monkeypatch.setattr("app.modules.auth.email_service.settings.RESEND_REPLY_TO_EMAIL", "")

    await AuthEmailService._send(
        to_email="user@example.com",
        subject="Subject",
        html="<p>Hello</p>",
        kind="verification",
    )

    assert fake_resend.api_key == "test-api-key"
    assert sent_payloads == [
        {
            "from": "noreply@mail.freeclaw.cloud",
            "to": ["user@example.com"],
            "subject": "Subject",
            "html": "<p>Hello</p>",
        }
    ]
