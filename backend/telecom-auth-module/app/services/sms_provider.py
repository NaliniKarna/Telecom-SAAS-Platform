"""SMS provider abstraction (gateway-agnostic dispatch).

The campaign service depends ONLY on the `SmsProvider` protocol and the
`get_sms_provider()` factory — never on a concrete gateway. Today the factory
returns `NullSmsProvider` (simulation): it accepts every message, returns a
synthetic provider id and a 'sent' status, so the whole pipeline
(resolve -> render -> dispatch -> persist) runs end to end WITHOUT a real SMS
gateway.

Adding a real provider later (SMPP bind, AkashSMS HTTP, Twilio REST, a generic
HTTP gateway) means implementing this one method and switching the factory — no
campaign service / route / UI change. The correlation seams are already present
on SmsMessage: `provider_message_id` (returned here) and `delivered_at` (set by
a future delivery-receipt webhook).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SendResult:
    """Outcome of handing one message to a provider.

    status is an SmsMessageStatus value ('sent' | 'delivered' | 'failed').
    Providers never raise for an undeliverable number — they return a failed
    result with error_details so the campaign records a per-recipient failure
    and continues.
    """
    status: str
    provider_message_id: str | None = None
    error_details: str | None = None


@dataclass
class DeliveryReceipt:
    """A delivery-status update arriving from a provider callback/webhook.

    Real gateways (SMPP DLR, AkashSMS / Twilio status webhooks, generic HTTP
    callbacks) post asynchronous status updates keyed by the provider's own
    message id. This is the normalized shape the platform ingests; each provider
    adapter is responsible for parsing its native payload into this object via
    `parse_callback()`. No real parser exists yet — see NullSmsProvider."""
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
        """Translate a provider's native delivery-callback payload into a
        normalized DeliveryReceipt. Returns None if the payload isn't a
        recognizable status update. Each real adapter implements this."""
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
        """Dev/test parser. Accepts a simple normalized shape:
        {"provider_message_id": "...", "status": "delivered"|"failed", "error": "..."}.
        A real adapter would parse the gateway's specific DLR/webhook format."""
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

    # Back-compat shim for the original tuple-based call site, if any remain.
    def dispatch(self, recipient_phone: str, content: str, sender_id: str | None = None) -> tuple[str, str | None]:
        result = self.send(recipient_phone=recipient_phone, content=content, sender_id=sender_id)
        return result.status, result.provider_message_id


# Future providers slot in here behind the same factory, e.g.:
#   class TwilioSmsProvider:  name = "twilio";  def send(...) -> SendResult: ...
#   class AkashSmsProvider:   name = "akashsms"; ...
#   class SmppSmsProvider:    name = "smpp"; ...
#   class HttpGatewayProvider: name = "http"; ...

_provider: SmsProvider | None = None


def get_sms_provider() -> SmsProvider:
    """Single place that decides which gateway is active. Swap the concrete
    class here (or read it from settings) when a real provider is wired in."""
    global _provider
    if _provider is None:
        _provider = NullSmsProvider()
    return _provider
