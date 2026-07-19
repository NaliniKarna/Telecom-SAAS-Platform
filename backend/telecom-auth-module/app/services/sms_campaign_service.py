"""SMS Campaign Engine service.

Lifecycle:
    draft ──schedule──▶ scheduled ──send──▶ processing ──▶ completed / failed
      │                     │
      └──────send───────────┘  (send-now works from draft or scheduled)
    draft / scheduled ──cancel──▶ cancelled

**Kafka integration (Phase 7):**
When `send_campaign()` is called, the service:
  1. Validates the campaign is ready (sender approved, template exists).
  2. Transitions status to `processing`.
  3. Publishes a `sms.campaign.created` event to Kafka.
  4. Returns immediately — the campaign processes ASYNCHRONOUSLY.

The Kafka worker (`app.workers.sms_campaign_worker`) picks up the event,
resolves recipients, fans out per-message `sms.message.send` events,
and those are dispatched through the SMS Forwarding API.

When Kafka is disabled (`KAFKA_ENABLED=false`), the service falls back to
the original synchronous dispatch loop (NullSmsProvider or AkashSmsProvider).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    SenderApprovalStatus,
    SenderStatus,
    SmsCampaignSource,
    SmsCampaignStatus,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.models.sms import SmsCampaign
from app.repositories.contact_list_repository import ContactListRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.sms_campaign_repository import (
    SmsCampaignRecipientRepository,
    SmsCampaignRepository,
    SmsMessageRepository,
)
from app.repositories.sms_repository import SmsSenderIdRepository, SmsTemplateRepository
from app.schemas.sms import CampaignCreate, CampaignUpdate
from app.services import sms_renderer
from app.services.audit_service import AuditService
from app.services.sms_provider import get_sms_provider
from app.services.sms_recipient_resolver import SmsRecipientResolver

logger = logging.getLogger(__name__)
_ENTITY = "sms_campaign"

_EDITABLE = SmsCampaignStatus.DRAFT.value
_SENDABLE = {SmsCampaignStatus.DRAFT.value, SmsCampaignStatus.SCHEDULED.value}


class SmsCampaignService:
    def __init__(self, session: AsyncSession, ctx=None, audit: AuditService | None = None):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.campaigns = SmsCampaignRepository(session, ctx)
        self.recipients = SmsCampaignRecipientRepository(session, ctx)
        self.messages = SmsMessageRepository(session, ctx)
        self.senders = SmsSenderIdRepository(session, ctx)
        self.templates = SmsTemplateRepository(session, ctx)
        self.resolver = SmsRecipientResolver(
            ContactRepository(session, ctx), ContactListRepository(session, ctx)
        )
        self.provider = get_sms_provider()

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    # ===================================================================== #
    # Read
    # ===================================================================== #
    async def list_campaigns(self, *, search=None, status=None, offset=0, limit=20):
        return await self.campaigns.search(search=search, status=status, offset=offset, limit=limit)

    async def get_campaign(self, campaign_id) -> SmsCampaign:
        c = await self.campaigns.get_by_id(campaign_id)
        if c is None:
            raise NotFoundError("Campaign not found")
        return c

    async def list_recipients(self, campaign_id, *, offset=0, limit=50):
        await self.get_campaign(campaign_id)
        return await self.recipients.list_for_campaign(campaign_id, offset=offset, limit=limit)

    async def list_messages(self, campaign_id, *, status=None, offset=0, limit=50):
        await self.get_campaign(campaign_id)
        return await self.messages.list_for_campaign(campaign_id, status=status, offset=offset, limit=limit)

    # ===================================================================== #
    # Create / edit (draft only)
    # ===================================================================== #
    async def create_campaign(self, data: CampaignCreate, *, actor_id=None, ip=None) -> SmsCampaign:
        if self._company_id is None:
            raise ValidationError("Campaigns are managed within a company")
        await self._validate_refs(data.sender_id, data.template_id)
        self._validate_source(data.source_type.value, data.source_list_id, data.contact_ids)

        campaign = await self.campaigns.create(
            company_id=self._company_id,
            name=data.name,
            sender_id=data.sender_id,
            template_id=data.template_id,
            source_type=data.source_type.value,
            source_list_id=(data.source_list_id if data.source_type == SmsCampaignSource.CONTACT_LIST else None),
            status=SmsCampaignStatus.DRAFT.value,
            created_by=actor_id,
        )
        if data.source_type == SmsCampaignSource.CONTACTS:
            await self._freeze_contacts(campaign, data.contact_ids)

        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": campaign.name, "source_type": campaign.source_type},
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    async def update_campaign(self, campaign_id, data: CampaignUpdate, *, actor_id=None, ip=None) -> SmsCampaign:
        campaign = await self.get_campaign(campaign_id)
        if campaign.status != _EDITABLE:
            raise ValidationError("Only draft campaigns can be edited")
        patch = data.model_dump(exclude_unset=True)
        contact_ids = patch.pop("contact_ids", None)
        source_list_id = patch.pop("source_list_id", None)
        if "source_type" in patch and patch["source_type"] is not None:
            patch["source_type"] = patch["source_type"].value if hasattr(patch["source_type"], "value") else patch["source_type"]
        if "sender_id" in patch or "template_id" in patch:
            await self._validate_refs(
                patch.get("sender_id", campaign.sender_id),
                patch.get("template_id", campaign.template_id),
            )
        effective_source = patch.get("source_type", campaign.source_type)
        if "source_type" in patch and patch["source_type"] is not None:
            patch["source_list_id"] = source_list_id if effective_source == SmsCampaignSource.CONTACT_LIST.value else None
        elif source_list_id is not None:
            patch["source_list_id"] = source_list_id
        if patch:
            await self.campaigns.update(campaign, **patch)
        if effective_source == SmsCampaignSource.CONTACTS.value and contact_ids is not None:
            await self._freeze_contacts(campaign, contact_ids)
        await self.audit.record(
            action="update", entity_type=_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in patch.items()},
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    # ===================================================================== #
    # Schedule / cancel
    # ===================================================================== #
    async def schedule_campaign(self, campaign_id, schedule_time: datetime, *, actor_id=None, ip=None) -> SmsCampaign:
        campaign = await self.get_campaign(campaign_id)
        if campaign.status not in _SENDABLE:
            raise ValidationError("Only draft or scheduled campaigns can be scheduled")
        if schedule_time.tzinfo is None:
            schedule_time = schedule_time.replace(tzinfo=timezone.utc)
        if schedule_time <= datetime.now(timezone.utc):
            raise ValidationError("Schedule time must be in the future")
        await self._assert_ready(campaign)
        await self.campaigns.update(
            campaign, status=SmsCampaignStatus.SCHEDULED.value, schedule_time=schedule_time,
        )
        await self.audit.record(
            action="schedule", entity_type=_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"schedule_time": schedule_time.isoformat()},
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    async def cancel_campaign(self, campaign_id, *, actor_id=None, ip=None) -> SmsCampaign:
        campaign = await self.get_campaign(campaign_id)
        if campaign.status not in _SENDABLE:
            raise ValidationError("Only draft or scheduled campaigns can be cancelled")
        await self.campaigns.update(campaign, status=SmsCampaignStatus.CANCELLED.value)
        await self.audit.record(
            action="cancel", entity_type=_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    # ===================================================================== #
    # Send now (execute) — Kafka-first, fallback to synchronous
    # ===================================================================== #
    async def send_campaign(self, campaign_id, *, actor_id=None, ip=None) -> SmsCampaign:
        campaign = await self.get_campaign(campaign_id)
        if campaign.status not in _SENDABLE:
            raise ValidationError("Only draft or scheduled campaigns can be sent")

        sender, template = await self._assert_ready(campaign)

        # Transition to processing BEFORE publishing to Kafka.
        await self.campaigns.update(campaign, status=SmsCampaignStatus.PROCESSING.value)
        await self.audit.record(
            action="send", entity_type=_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=campaign.company_id, ip_address=ip,
            new_values={"mode": "kafka" if self._kafka_enabled else "sync"},
        )
        await self.session.commit()
        await self.session.refresh(campaign)

        if self._kafka_enabled:
            # ── Kafka path: publish event and return immediately ──
            await self._publish_campaign_event(campaign, actor_id=actor_id)
            logger.info(
                "Campaign %s queued to Kafka for async processing", campaign.id
            )
            return campaign
        else:
            # ── Fallback: synchronous dispatch (NullProvider / dev mode) ──
            return await self._execute_sync(campaign, sender, template, actor_id=actor_id, ip=ip)

    @property
    def _kafka_enabled(self) -> bool:
        from app.core.config import settings
        return settings.KAFKA_ENABLED

    async def _publish_campaign_event(self, campaign: SmsCampaign, *, actor_id=None) -> None:
        """Publish sms.campaign.created event to Kafka."""
        from app.core.kafka import KafkaTopics, get_producer
        producer = await get_producer()
        await producer.produce(
            KafkaTopics.SMS_CAMPAIGN_CREATED,
            key=str(campaign.company_id),
            value={
                "campaign_id": str(campaign.id),
                "company_id": str(campaign.company_id),
                "actor_id": str(actor_id) if actor_id else None,
            },
        )

    # ===================================================================== #
    # Synchronous execution fallback (original flow)
    # ===================================================================== #
    async def _execute_sync(self, campaign: SmsCampaign, sender, template, *, actor_id=None, ip=None) -> SmsCampaign:
        """Synchronous campaign execution — used when Kafka is disabled."""
        company_name = await self._company_name()

        # Freeze recipients
        if campaign.source_type == SmsCampaignSource.CONTACT_LIST.value:
            resolved = await self.resolver.resolve(
                source_type=campaign.source_type,
                source_list_id=campaign.source_list_id,
                contact_ids=None,
            )
            await self.recipients.delete_for_campaign(campaign.id)
            await self.recipients.bulk_add([
                {"campaign_id": campaign.id, "contact_id": r.contact_id,
                 "phone_e164": r.phone_e164, "resolved_name": r.resolved_name}
                for r in resolved
            ])
        else:
            existing = await self.recipients.all_for_campaign(campaign.id)
            contact_ids = [r.contact_id for r in existing if r.contact_id is not None]
            resolved = await self.resolver.resolve(
                source_type=campaign.source_type, source_list_id=None, contact_ids=contact_ids,
            )
            await self.recipients.delete_for_campaign(campaign.id)
            await self.recipients.bulk_add([
                {"campaign_id": campaign.id, "contact_id": r.contact_id,
                 "phone_e164": r.phone_e164, "resolved_name": r.resolved_name}
                for r in resolved
            ])

        # Dispatch per recipient
        sent = delivered = failed = 0
        now = datetime.now(timezone.utc)
        message_rows = []
        for r in resolved:
            content = sms_renderer.render_template(
                template.body,
                sms_renderer.build_recipient_values(
                    name=r.resolved_name, phone=r.phone_e164, company=company_name,
                ),
            )
            result = self.provider.send(
                recipient_phone=r.phone_e164, content=content, sender_id=sender.sender_id,
            )
            is_failed = result.status == "failed"
            message_rows.append({
                "company_id": campaign.company_id,
                "campaign_id": campaign.id,
                "recipient_phone": r.phone_e164,
                "sender_id": sender.sender_id,
                "content": content,
                "status": result.status,
                "error_details": result.error_details,
                "provider_message_id": result.provider_message_id,
                "sent_at": None if is_failed else now,
                "delivered_at": now if result.status == "delivered" else None,
            })
            if is_failed:
                failed += 1
            else:
                sent += 1
                if result.status == "delivered":
                    delivered += 1
        await self.messages.bulk_add(message_rows)

        total = len(resolved)
        final = (
            SmsCampaignStatus.FAILED.value
            if total > 0 and failed == total
            else SmsCampaignStatus.COMPLETED.value
        )
        await self.campaigns.update(
            campaign,
            status=final,
            total_recipients=total,
            sent_count=sent,
            delivered_count=delivered,
            failed_count=failed,
        )
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign

    # ===================================================================== #
    # Helpers
    # ===================================================================== #
    async def _validate_refs(self, sender_id, template_id):
        if sender_id is not None and await self.senders.get_by_id(sender_id) is None:
            raise ValidationError("Sender ID not found")
        if template_id is not None and await self.templates.get_by_id(template_id) is None:
            raise ValidationError("Template not found")

    @staticmethod
    def _validate_source(source_type: str, source_list_id, contact_ids):
        if source_type == SmsCampaignSource.CONTACT_LIST.value and not source_list_id:
            raise ValidationError("A contact list is required for this source")
        if source_type == SmsCampaignSource.CONTACTS.value and not contact_ids:
            raise ValidationError("At least one contact is required for this source")

    async def _assert_ready(self, campaign: SmsCampaign):
        if campaign.sender_id is None:
            raise ValidationError("Campaign has no sender ID")
        sender = await self.senders.get_by_id(campaign.sender_id)
        if sender is None:
            raise ValidationError("Sender ID not found")
        if sender.approval_status != SenderApprovalStatus.APPROVED.value:
            raise ValidationError("Sender ID is not approved")
        if sender.status != SenderStatus.ACTIVE.value:
            raise ValidationError("Sender ID is inactive")
        if campaign.template_id is None:
            raise ValidationError("Campaign has no template")
        template = await self.templates.get_by_id(campaign.template_id)
        if template is None:
            raise ValidationError("Template not found")
        return sender, template

    async def _company_name(self) -> str | None:
        from app.models.company import Company
        from sqlalchemy import select
        if self._company_id is None:
            return None
        return (await self.session.execute(
            select(Company.name).where(Company.id == self._company_id)
        )).scalar_one_or_none()

    async def _freeze_contacts(self, campaign: SmsCampaign, contact_ids):
        resolved = await self.resolver.resolve(
            source_type=SmsCampaignSource.CONTACTS.value,
            source_list_id=None,
            contact_ids=list(contact_ids),
        )
        await self.recipients.delete_for_campaign(campaign.id)
        await self.recipients.bulk_add([
            {"campaign_id": campaign.id, "contact_id": r.contact_id,
             "phone_e164": r.phone_e164, "resolved_name": r.resolved_name}
            for r in resolved
        ])