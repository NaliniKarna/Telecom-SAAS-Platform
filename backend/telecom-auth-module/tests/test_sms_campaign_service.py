"""Unit tests for the SMS Campaign Engine execute/send contract.

These exercise SmsCampaignService.send_campaign -> _execute against the current
service API (campaign logic lives here, not in SmsService). The integration
seams that touch the DB / gateway are stubbed so the test asserts the observable
contract only: one SmsMessage row per resolved recipient, correct per-recipient
status + provider correlation id, accurate campaign counters, and the final
status transition (COMPLETED, or FAILED when every recipient fails).
"""
from types import SimpleNamespace

import pytest

from app.core.constants import (
    SmsCampaignSource,
    SmsCampaignStatus,
    SmsMessageStatus,
)
from app.models.sms import SmsCampaign
from app.services.sms_campaign_service import SmsCampaignService
from app.services.sms_provider import SendResult


class FakeSession:
    """Minimal async session: just enough for _execute's commit/refresh."""

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


def _build_service(*, send_result: SendResult, recipients):
    """Construct a service with every DB/gateway seam stubbed.

    `campaigns.update` applies the kwargs onto the campaign object so status and
    counter transitions are observable; `messages.bulk_add` captures the rows.
    """
    service = SmsCampaignService(
        FakeSession(),
        SimpleNamespace(company_id="company-1", is_super_admin=False),
    )

    captured = {"messages": None}

    async def assert_ready(campaign):
        sender = SimpleNamespace(sender_id="ACME")
        template = SimpleNamespace(body="Hello {{name}}", id="template-1")
        return sender, template

    async def company_name():
        return "Acme Inc"

    async def resolve(*, source_type, source_list_id, contact_ids):
        return recipients

    async def update(obj, **fields):
        for key, value in fields.items():
            setattr(obj, key, value)
        return obj

    async def bulk_add_messages(rows):
        captured["messages"] = rows
        return None

    async def noop(*args, **kwargs):
        return None

    service._assert_ready = assert_ready
    service._company_name = company_name
    service.resolver.resolve = resolve
    service.campaigns.update = update
    service.recipients.delete_for_campaign = noop
    service.recipients.bulk_add = noop
    service.recipients.all_for_campaign = lambda *a, **k: _async_list([])
    service.messages.bulk_add = bulk_add_messages
    service.audit.record = noop
    service.provider = SimpleNamespace(
        send=lambda **kwargs: send_result, name="fake"
    )
    return service, captured


def _async_list(value):
    async def _coro():
        return value
    return _coro()


def _campaign():
    return SmsCampaign(
        id="campaign-1",
        company_id="company-1",
        name="Launch",
        status=SmsCampaignStatus.DRAFT.value,
        source_type=SmsCampaignSource.CONTACT_LIST.value,
        source_list_id="list-1",
        sender_id="sender-1",
        template_id="template-1",
    )


@pytest.mark.asyncio
async def test_send_campaign_records_messages_and_completes():
    campaign = _campaign()
    recipients = [
        SimpleNamespace(contact_id="c1", phone_e164="+15551234567", resolved_name="Asha"),
        SimpleNamespace(contact_id="c2", phone_e164="+15557654321", resolved_name="Bina"),
    ]
    service, captured = _build_service(
        send_result=SendResult(status="sent", provider_message_id="provider-123"),
        recipients=recipients,
    )

    async def get_campaign(campaign_id):
        return campaign

    service.campaigns.get_by_id = get_campaign

    result = await service.send_campaign(campaign.id, actor_id="user-1")

    # Status transitioned to COMPLETED.
    assert result.status == SmsCampaignStatus.COMPLETED.value
    # One message row per resolved recipient.
    assert captured["messages"] is not None
    assert len(captured["messages"]) == len(recipients)
    # Per-recipient status + provider correlation id are recorded.
    first = captured["messages"][0]
    assert first["status"] == SmsMessageStatus.SENT.value
    assert first["provider_message_id"] == "provider-123"
    assert first["sender_id"] == "ACME"          # snapshot of the sender label
    assert first["content"] == "Hello Asha"      # rendered + snapshotted body
    # Counters are denormalized onto the campaign.
    assert result.total_recipients == 2
    assert result.sent_count == 2
    assert result.failed_count == 0


@pytest.mark.asyncio
async def test_send_campaign_marks_failed_when_all_recipients_fail():
    campaign = _campaign()
    recipients = [
        SimpleNamespace(contact_id="c1", phone_e164="+15551234567", resolved_name="Asha"),
    ]
    service, captured = _build_service(
        send_result=SendResult(status="failed", error_details="rejected"),
        recipients=recipients,
    )

    async def get_campaign(campaign_id):
        return campaign

    service.campaigns.get_by_id = get_campaign

    result = await service.send_campaign(campaign.id, actor_id="user-1")

    assert result.status == SmsCampaignStatus.FAILED.value
    assert result.failed_count == 1
    assert result.sent_count == 0
    assert captured["messages"][0]["status"] == SmsMessageStatus.FAILED.value
    assert captured["messages"][0]["sent_at"] is None
