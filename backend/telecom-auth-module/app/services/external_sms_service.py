"""External (API-key authenticated) SMS send — orchestration only.

This module contains ZERO SMS-sending logic of its own. It exists purely to
adapt a single "send one SMS" request from a programmatic caller into the
exact same create-campaign -> send-campaign call sequence the Angular
console already uses (app.services.sms_campaign_service.SmsCampaignService),
so every downstream step — Kafka publish, the campaign worker, the AkashSMS
forwarding call — is the one and only pipeline that exists in this codebase.
Nothing here talks to Kafka, a provider, or the SMS Forwarding API directly.

The only new behavior is the adaptation itself:
  1. Resolve-or-create a Contact for the destination number (reuses
     ContactService — normal contact management, not SMS logic).
  2. Wrap that single contact as a one-recipient campaign
     (SmsCampaignService.create_campaign, source_type=CONTACTS).
  3. Send it immediately (SmsCampaignService.send_campaign) — this is the
     existing method that decides Kafka-vs-sync and does the actual
     publish; this module never touches that decision.

Tenant isolation: every repository/service here is constructed with a
TenantContext scoped to the API key's company_id, exactly as a logged-in
Company Admin's session would be. There is no code path that lets a request
read or write another company's data.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SmsCampaignSource
from app.core.exceptions import CompanyInactiveError, NotFoundError
from app.core.rbac import TenantContext
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import ContactCreate
from app.schemas.external_sms import ExternalSmsSendRequest
from app.services.audit_service import AuditService
from app.services.contact_service import ContactService
from app.services.sms_campaign_service import SmsCampaignService


@dataclass
class ExternalSmsResult:
    campaign_id: uuid.UUID
    contact_id: uuid.UUID
    status: str


class ExternalSmsService:
    def __init__(self, session: AsyncSession, company_id):
        self.session = session
        self.company_id = company_id
        # Synthetic, non-human context. Never accepted by the JWT chain
        # (get_current_user is never invoked on this path), so it can't be
        # confused with a real logged-in session — it exists solely to give
        # the existing tenant-scoped repositories/services the company_id
        # they need to filter by. roles=[] / permissions=set() means
        # is_super_admin is False, so tenant scoping is fully enforced, not
        # bypassed.
        self.ctx = TenantContext(
            user_id="api-key",
            company_id=str(company_id),
            roles=[],
            permissions=set(),
        )
        self._audit = AuditService(session)
        self.contacts = ContactService(
            session, ContactRepository(session, self.ctx), self._audit,
        )
        self.campaigns = SmsCampaignService(session, self.ctx, self._audit)

    async def assert_company_active(self) -> None:
        company = await CompanyRepository(self.session).get_by_id(self.company_id)
        if company is None:
            raise NotFoundError("Company not found")
        if not company.is_active:
            raise CompanyInactiveError(
                "This company's account is not active; SMS sending is disabled."
            )

    async def send(
        self, payload: ExternalSmsSendRequest, *, client_ip: Optional[str] = None,
    ) -> ExternalSmsResult:
        contact = await self._resolve_or_create_contact(payload, client_ip=client_ip)

        from app.schemas.sms import CampaignCreate  # local import avoids a cycle at module load

        campaign = await self.campaigns.create_campaign(
            CampaignCreate(
                name=f"External API — {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC",
                sender_id=payload.sender_id,
                template_id=payload.template_id,
                source_type=SmsCampaignSource.CONTACTS,
                contact_ids=[contact.id],
            ),
            actor_id=None,  # no human actor — this request was authenticated by API key
            ip=client_ip,
        )
        sent = await self.campaigns.send_campaign(campaign.id, actor_id=None, ip=client_ip)

        return ExternalSmsResult(
            campaign_id=sent.id, contact_id=contact.id, status=sent.status,
        )

    async def _resolve_or_create_contact(
        self, payload: ExternalSmsSendRequest, *, client_ip: Optional[str],
    ):
        # Reuse the exact normalization ContactService.create_contact() uses
        # internally, so "is this a duplicate" is checked on the same
        # normalized value the service would derive — no separate parsing
        # logic invented here.
        mobile_e164, _landline_e164, _ntype = ContactService._normalize(payload.to, None)
        if not mobile_e164:
            from app.core.exceptions import ValidationError
            raise ValidationError(f"'{payload.to}' is not a valid destination number")

        existing = await self.contacts.repo.find_duplicate(
            mobile_e164=mobile_e164, email=None,
        )
        if existing is not None:
            return existing

        return await self.contacts.create_contact(
            ContactCreate(first_name=payload.recipient_name, mobile=payload.to),
            actor_id=None,
            ip=client_ip,
        )