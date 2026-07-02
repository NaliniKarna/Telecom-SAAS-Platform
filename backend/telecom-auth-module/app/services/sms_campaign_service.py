"""SMS Campaign Engine service.

Lifecycle:
    draft ──schedule──▶ scheduled ──send──▶ processing ──▶ completed / failed
      │                     │
      └──────send───────────┘  (send-now works from draft or scheduled)
    draft / scheduled ──cancel──▶ cancelled

Editing is allowed only while a campaign is in draft. Sending validates that the
sender is approved + active and the template exists, freezes the recipient set
(resolution layer: dedupe + snapshot), renders per-recipient content (snapshot
the sender label + body at send time), dispatches through the SmsProvider seam
(NullSmsProvider today), persists one SmsMessage per recipient, and updates the
campaign counters/status.

Tenant isolation comes from the repositories' context. All state changes are
audited: create / update / schedule / send (execute) / cancel.
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
        await self.get_campaign(campaign_id)  # tenant existence check
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
        # For an individual-contacts source, snapshot the selection now so the
        # draft remembers it (re-resolved/refreshed at send time).
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
        # Resolve the effective source type for source persistence.
        effective_source = patch.get("source_type", campaign.source_type)
        if "source_type" in patch and patch["source_type"] is not None:
            # Source type is being changed: reset the list link accordingly.
            patch["source_list_id"] = source_list_id if effective_source == SmsCampaignSource.CONTACT_LIST.value else None
        elif source_list_id is not None:
            # Same source, but a new list was explicitly provided.
            patch["source_list_id"] = source_list_id
        if patch:
            await self.campaigns.update(campaign, **patch)
        # If a contacts selection was supplied, refreeze the snapshot rows.
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
    # Send now (execute)
    # ===================================================================== #
    async def send_campaign(self, campaign_id, *, actor_id=None, ip=None) -> SmsCampaign:
        campaign = await self.get_campaign(campaign_id)
        if campaign.status not in _SENDABLE:
            raise ValidationError("Only draft or scheduled campaigns can be sent")
        return await self._execute(campaign, actor_id=actor_id, ip=ip)

    async def _execute(self, campaign: SmsCampaign, *, actor_id=None, ip=None) -> SmsCampaign:
        sender, template = await self._assert_ready(campaign)
        company_name = await self._company_name()

        await self.campaigns.update(campaign, status=SmsCampaignStatus.PROCESSING.value)

        # Freeze recipients from the campaign source (dedupe + snapshot).
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
            # Contacts source: re-resolve from the snapshotted contact_ids to
            # refresh phone/name, then rewrite the frozen rows.
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

        # Dispatch per recipient; persist one message each.
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
                "sender_id": sender.sender_id,  # snapshot of sender label
                "content": content,             # snapshot of rendered body
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
        await self.audit.record(
            action="send", entity_type=_ENTITY, entity_id=campaign.id,
            actor_id=actor_id, company_id=campaign.company_id, ip_address=ip,
            new_values={"total": total, "sent": sent, "delivered": delivered, "failed": failed},
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
        """Snapshot an individual-contacts selection as recipient rows (deduped
        by phone). Re-resolved/refreshed at send so the snapshot stays current
        for drafts while preserving historical integrity once sent."""
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
