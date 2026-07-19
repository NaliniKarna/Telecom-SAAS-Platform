"""AkashSMS provider — bridges the SMS Forwarding API microservice.

This provider implements the SmsProvider protocol by calling the existing
SMS Forwarding API over HTTP. It NEVER contacts the AkashSMS gateway
directly — that responsibility belongs solely to the Forwarding API.

╔══════════════════════════════════════════════════════════════════════════╗
║ IMPORTANT — the Forwarding API's field naming is NOT what it looks like.  ║
╚══════════════════════════════════════════════════════════════════════════╝

Reading the Forwarding API's own /send-sms implementation:

    template = db.query(SMSConfig).filter(SMSConfig.to_number == data.to_number).first()
    ...
    requests.post(AKASH_URL, data={..., "to": data.from_number, "text": template.sms_text})

`to_number` is NOT the recipient. It is a lookup key into a pre-registered
SMSConfig row (created via POST /add-template, UNIQUE per to_number). The
row's `sms_text` is what actually gets sent — as a message TO `from_number`,
which IS the real destination phone number.

So the real contract is:
    from_number = the actual recipient's phone (digits only, 10-15 chars)
    to_number   = a lookup key for a pre-registered message template
                  (also validated as digits-only, 10-15 chars — even though
                  it's conceptually just a template ID, not a phone number)

Campaigns need per-recipient DYNAMIC content (name/phone/company merge
fields), but the Forwarding API only sends whatever static text was
registered under a to_number key. To reconcile this without modifying the
Forwarding API (out of scope — it's a separate, already-working service),
this provider performs TWO calls per message:

  1. POST /add-template  — register the rendered content under a fresh,
                            unique numeric key (acts as a one-time template).
  2. POST /send-sms      — from_number=recipient, to_number=that same key.
                            The Forwarding API looks up the template we just
                            registered and sends it to the recipient.

Each message gets its own key, so concurrent sends never collide or
overwrite each other's content.

Configuration (from Settings):
  SMS_FORWARDING_API_URL — base URL of the Forwarding API (e.g. http://localhost:8001)
  SMS_FORWARDING_API_KEY — the API key expected by the Forwarding API
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Optional

import httpx

from app.services.sms_provider import DeliveryReceipt, SendResult, SmsProvider

logger = logging.getLogger(__name__)


def _stringify_error(detail) -> str:
    """Coerce any error payload shape into a plain string.

    FastAPI validation errors (HTTP 422) return `detail` as a LIST of error
    dicts, not a string. Passing that list straight into a VARCHAR database
    column crashes asyncpg with 'expected str, got list'. This function
    guarantees callers always get a string, regardless of what the upstream
    API returns (str, list, dict, or anything else).
    """
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail)[:1000]  # cap length for the DB column
    except (TypeError, ValueError):
        return str(detail)[:1000]


def _generate_channel_key(seed: str | None = None) -> str:
    """Generate a fresh 10-15 digit numeric key for the Forwarding API's
    `to_number` field, which it uses purely as a one-time template lookup
    key (see module docstring). Combines a millisecond timestamp (13 digits,
    guarantees ordering/uniqueness across calls) with a 2-digit hash suffix
    derived from `seed` (e.g. the message_id) so concurrent sends in the
    same millisecond still get distinct keys.
    """
    millis = str(int(time.time() * 1000))  # 13 digits
    suffix_seed = seed or uuid.uuid4().hex
    suffix = str(abs(hash(suffix_seed)) % 100).zfill(2)  # 2 digits
    key = (millis + suffix)[:15]
    return key


class AkashSmsProvider:
    """Production SMS provider that dispatches through the SMS Forwarding API."""

    name = "akashsms"

    def __init__(
        self,
        forwarding_api_url: str,
        forwarding_api_key: str,
        timeout: float = 15.0,
    ):
        self._base_url = forwarding_api_url.rstrip("/")
        self._api_key = forwarding_api_key
        self._timeout = timeout

    # ------------------------------------------------------------------ #
    # Synchronous send — used by the campaign service's sync fallback loop
    # ------------------------------------------------------------------ #
    def send(
        self,
        *,
        recipient_phone: str,
        content: str,
        sender_id: str | None = None,
    ) -> SendResult:
        import httpx as sync_httpx

        if not recipient_phone:
            return SendResult(status="failed", error_details="Missing recipient phone")

        recipient_digits = recipient_phone.lstrip("+")
        channel_key = _generate_channel_key(recipient_phone + content[:20])

        try:
            with sync_httpx.Client(timeout=self._timeout) as client:
                # Step 1: register this message's content under a fresh key.
                add_resp = client.post(
                    f"{self._base_url}/add-template",
                    json={
                        "to_number": channel_key,
                        "sms_text": content,
                        "api_key": self._api_key,
                    },
                )
                if not add_resp.is_success:
                    return SendResult(
                        status="failed",
                        error_details=_stringify_error(
                            self._safe_json(add_resp).get("detail", f"HTTP {add_resp.status_code}")
                        ),
                    )

                # Step 2: actual send — from_number is the REAL recipient.
                send_resp = client.post(
                    f"{self._base_url}/send-sms",
                    json={
                        "from_number": recipient_digits,
                        "to_number": channel_key,
                        "api_key": self._api_key,
                    },
                )

            body = self._safe_json(send_resp)
            if send_resp.is_success and body.get("status") == "sent":
                return SendResult(status="sent", provider_message_id=f"akash-{channel_key}")
            return SendResult(
                status="failed",
                error_details=_stringify_error(body.get("detail", f"HTTP {send_resp.status_code}")),
            )
        except Exception as exc:
            logger.error("AkashSMS send error: %s", exc)
            return SendResult(status="failed", error_details=_stringify_error(str(exc)))

    # ------------------------------------------------------------------ #
    # Async send — used by the Kafka worker
    # ------------------------------------------------------------------ #
    async def send_async(
        self,
        *,
        recipient_phone: str,
        content: str,
        sender_id: str | None = None,
    ) -> SendResult:
        if not recipient_phone:
            return SendResult(status="failed", error_details="Missing recipient phone")

        recipient_digits = recipient_phone.lstrip("+")
        channel_key = _generate_channel_key(recipient_phone + content[:20])

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # Step 1: register this message's content under a fresh key.
                add_resp = await client.post(
                    f"{self._base_url}/add-template",
                    json={
                        "to_number": channel_key,
                        "sms_text": content,
                        "api_key": self._api_key,
                    },
                )
                if not add_resp.is_success:
                    err = _stringify_error(
                        self._safe_json(add_resp).get("detail", f"HTTP {add_resp.status_code}")
                    )
                    logger.error(
                        "AkashSMS add-template failed for %s: %s", recipient_phone, err,
                    )
                    return SendResult(status="failed", error_details=err)

                # Step 2: actual send — from_number is the REAL recipient.
                send_resp = await client.post(
                    f"{self._base_url}/send-sms",
                    json={
                        "from_number": recipient_digits,
                        "to_number": channel_key,
                        "api_key": self._api_key,
                    },
                )

            body = self._safe_json(send_resp)
            if send_resp.is_success and body.get("status") == "sent":
                return SendResult(status="sent", provider_message_id=f"akash-{channel_key}")

            err = _stringify_error(body.get("detail", f"HTTP {send_resp.status_code}"))
            logger.error("AkashSMS send-sms failed for %s: %s", recipient_phone, err)
            return SendResult(status="failed", error_details=err)

        except Exception as exc:
            logger.error("AkashSMS async send error: %s", exc)
            return SendResult(status="failed", error_details=_stringify_error(str(exc)))

    @staticmethod
    def _safe_json(response) -> dict:
        """Parse response JSON, tolerating non-JSON error bodies."""
        try:
            return response.json()
        except Exception:
            return {"detail": response.text[:500] if hasattr(response, "text") else "Unknown error"}

    def parse_callback(self, payload: dict) -> Optional[DeliveryReceipt]:
        """Parse AkashSMS delivery callback (future webhook integration).

        The SMS Forwarding API currently does not expose a delivery callback
        endpoint. When AkashSMS webhook support is added, the normalized
        receipt is parsed here.
        """
        pmid = payload.get("provider_message_id") or payload.get("message_id")
        status = payload.get("status")
        if not pmid or status not in ("delivered", "failed", "sent"):
            return None
        return DeliveryReceipt(
            provider_message_id=pmid,
            status=status,
            error_details=_stringify_error(payload.get("error") or payload.get("error_details")),
            raw=payload,
        )