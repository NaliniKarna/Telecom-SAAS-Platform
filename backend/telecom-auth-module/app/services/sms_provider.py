"""SMS provider abstraction (gateway-agnostic dispatch).

The campaign service depends ONLY on the `SmsProvider` protocol and the
`get_sms_provider()` factory — never on a concrete gateway.

Providers:
  NullSmsProvider   — simulation (no network I/O). Default.
  AkashSmsProvider  — production bridge to SMS Forwarding API (→ AkashSMS).

The factory reads settings.SMS_PROVIDER to decide which provider is active.
Switching from simulation to production requires only an env var change.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SendResult:
    """Outcome of handing one message to a provider."""
    status: str
    provider_message_id: str | None = None
    error_details: str | None = None


@dataclass
class DeliveryReceipt:
    """A delivery-status update arriving from a provider callback/webhook."""
    provider_message_id: str
    status: str               # delivered | failed | sent
    error_details: str | None = None
    raw: dict | None = None


class SmsProvider(Protocol):
    """Interface every gateway implements."""
    name: str

    def send(self, *, recipient_phone: str, content: str, sender_id: str | None = None) -> SendResult:
        ...

    def parse_callback(self, payload: dict) -> "DeliveryReceipt | None":
        ...


class NullSmsProvider:
    """Simulation provider used for development/testing. No network I/O."""
    name = "null"

    def send(self, *, recipient_phone: str, content: str, sender_id: str | None = None) -> SendResult:
        if not recipient_phone:
            return SendResult(status="failed", error_details="Missing recipient phone")
        return SendResult(
            status="sent",
            provider_message_id=f"sim-{uuid.uuid4().hex}",
        )

    def parse_callback(self, payload: dict) -> "DeliveryReceipt | None":
        pmid = payload.get("provider_message_id") or payload.get("message_id")
        status = payload.get("status")
        if not pmid or status not in ("delivered", "failed", "sent"):
            return None
        return DeliveryReceipt(
            provider_message_id=pmid,
            status=status,
            error_details=payload.get("error") or payload.get("error_details"),
            raw=payload,
        )

    def dispatch(self, recipient_phone: str, content: str, sender_id: str | None = None) -> tuple[str, str | None]:
        result = self.send(recipient_phone=recipient_phone, content=content, sender_id=sender_id)
        return result.status, result.provider_message_id


_provider: SmsProvider | None = None


def get_sms_provider() -> SmsProvider:
    """Factory that returns the active SMS provider based on settings.

    "null"     → NullSmsProvider (default, no SMS sent)
    "akashsms" → AkashSmsProvider (calls SMS Forwarding API → AkashSMS)
    """
    global _provider
    if _provider is None:
        from app.core.config import settings

        if settings.SMS_PROVIDER == "akashsms":
            from app.services.akashsms_provider import AkashSmsProvider
            _provider = AkashSmsProvider(
                forwarding_api_url=settings.SMS_FORWARDING_API_URL,
                forwarding_api_key=settings.SMS_FORWARDING_API_KEY,
            )
        else:
            _provider = NullSmsProvider()

    return _provider
