"""Email delivery helpers for account-security flows."""
from __future__ import annotations

from app.core.config import settings


class AuthEmailService:
    """Send account-security emails through Resend."""

    @staticmethod
    def _build_url(path: str, token: str) -> str:
        base_url = settings.APP_FRONTEND_URL.rstrip("/")
        return f"{base_url}/{path}?token={token}"

    @staticmethod
    def _ensure_email_config() -> None:
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY is not configured")
        if not settings.RESEND_FROM_EMAIL:
            raise RuntimeError("RESEND_FROM_EMAIL is not configured")

    @classmethod
    async def _send(cls, *, to_email: str, subject: str, html: str) -> None:
        cls._ensure_email_config()

        import resend

        resend.api_key = settings.RESEND_API_KEY
        payload = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        if settings.RESEND_REPLY_TO_EMAIL:
            payload["reply_to"] = settings.RESEND_REPLY_TO_EMAIL

        resend.Emails.send(payload)

    @classmethod
    async def send_verification_email(cls, to_email: str, token: str) -> None:
        verification_url = cls._build_url("verify-email", token)
        html = (
            "<p>Please verify your email address for JobPilot.</p>"
            f'<p><a href="{verification_url}">Verify email</a></p>'
            "<p>This link expires in 24 hours. If you did not create this account, you can ignore this email.</p>"
            f"<p>{verification_url}</p>"
        )
        await cls._send(to_email=to_email, subject="Verify your JobPilot email", html=html)

    @classmethod
    async def send_password_reset_email(cls, to_email: str, token: str) -> None:
        reset_url = cls._build_url("reset-password", token)
        html = (
            "<p>We received a request to reset your JobPilot password.</p>"
            f'<p><a href="{reset_url}">Reset password</a></p>'
            "<p>This link expires in 1 hour. If you did not request this, you can ignore this email.</p>"
            f"<p>{reset_url}</p>"
        )
        await cls._send(to_email=to_email, subject="Reset your JobPilot password", html=html)

    @classmethod
    async def send_email_change_confirmation_email(cls, to_email: str, token: str) -> None:
        confirm_url = cls._build_url("change-email-confirm", token)
        html = (
            "<p>Please confirm your new email address for JobPilot.</p>"
            f'<p><a href="{confirm_url}">Confirm new email</a></p>'
            "<p>This link expires in 24 hours. If you did not request this change, you can ignore this email.</p>"
            f"<p>{confirm_url}</p>"
        )
        await cls._send(
            to_email=to_email,
            subject="Confirm your new JobPilot email",
            html=html,
        )
