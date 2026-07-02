"""Email delivery service.

Thin transport over SMTP. When EMAIL_ENABLED is False (the default, for local
dev), it logs the message and any link instead of sending — so password-reset
and verification flows are testable without a mail server.

Designed to be called from a FastAPI BackgroundTask so the request returns
immediately. Stateless and cheap to instantiate per request.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self) -> None:
        self._enabled = settings.EMAIL_ENABLED

    # ----- public API -------------------------------------------------------
    def send_password_reset(self, to_email: str, token: str) -> None:
        link = f"{settings.FRONTEND_BASE_URL}/auth/reset-password?token={token}"
        self._send(
            to_email,
            subject="Reset your password",
            body=(
                "We received a request to reset your password.\n\n"
                f"Reset it here (valid for "
                f"{settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes):\n"
                f"{link}\n\n"
                "If you didn't request this, you can ignore this email."
            ),
            link=link,
        )

    def send_email_verification(self, to_email: str, token: str) -> None:
        link = f"{settings.FRONTEND_BASE_URL}/auth/verify-email?token={token}"
        self._send(
            to_email,
            subject="Verify your email address",
            body=(
                "Welcome! Please confirm your email address.\n\n"
                f"Verify here:\n{link}\n\n"
                "If you didn't create an account, you can ignore this email."
            ),
            link=link,
        )

    def send_invite(self, to_email: str, token: str) -> None:
        """Invite a new company user to set their password and activate.

        Reusable for future provider integrations: only the link/template lives
        here; the token is minted by the caller. In dev (EMAIL_ENABLED=False)
        the link is logged so invites are testable without a mail server.
        """
        link = f"{settings.FRONTEND_BASE_URL}/auth/accept-invite?token={token}"
        self._send(
            to_email,
            subject="You've been invited",
            body=(
                "You've been invited to join your company's workspace.\n\n"
                f"Set your password and get started here:\n{link}\n\n"
                "If you weren't expecting this, you can ignore this email."
            ),
            link=link,
        )

    # ----- transport --------------------------------------------------------
    def _send(self, to_email: str, subject: str, body: str, link: str) -> None:
        if not self._enabled:
            # Dev mode: don't send; surface the link in logs for manual testing.
            logger.warning(
                "EMAIL_ENABLED is false — not sending. to=%s subject=%r link=%s",
                to_email,
                subject,
                link,
            )
            return

        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=10
            ) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(message)
            logger.info("email_sent to=%s subject=%r", to_email, subject)
        except Exception:
            # Never let a mail failure break the auth flow; log and move on.
            logger.exception(
                "email_send_failed to=%s subject=%r", to_email, subject
            )