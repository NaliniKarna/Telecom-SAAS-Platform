"""SMS Foundation service: sender IDs + templates.

Tenant-scoped via the repositories' context. Sender IDs follow an approval
workflow — a company admin creates one (status PENDING); only a super admin
approves/rejects (a company admin cannot self-approve). Templates support
auto-extracted variables, duplicate, and preview. All mutations are audited.

Campaigns, message sending, and analytics are intentionally NOT part of this
module.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    SenderApprovalStatus,
    SenderStatus,
    SmsTemplateStatus,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.sms import SmsSenderId, SmsTemplate
from app.repositories.sms_repository import (
    SmsSenderIdRepository,
    SmsTemplateRepository,
)
from app.schemas.sms import (
    SenderIdCreate,
    SenderIdUpdate,
    TemplateCreate,
    TemplatePreviewRequest,
    TemplateUpdate,
)
from app.services.audit_service import AuditService
from app.services.sms_renderer import extract_variables, render_template

logger = logging.getLogger(__name__)

_SENDER_ENTITY = "sms_sender_id"
_TEMPLATE_ENTITY = "sms_template"


class SmsService:
    def __init__(self, session: AsyncSession, ctx=None, audit: AuditService | None = None):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.sender_ids = SmsSenderIdRepository(session, ctx)
        self.templates = SmsTemplateRepository(session, ctx)

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    # ===================================================================== #
    # Sender IDs
    # ===================================================================== #
    async def list_sender_ids(self, *, search=None, status=None, approval_status=None,
                              offset: int = 0, limit: int = 20):
        return await self.sender_ids.search(
            search=search, status=status, approval_status=approval_status,
            offset=offset, limit=limit,
        )

    async def get_sender_id(self, sender_id) -> SmsSenderId:
        sender = await self.sender_ids.get_by_id(sender_id)
        if sender is None:
            raise NotFoundError("Sender ID not found")
        return sender

    async def create_sender_id(self, data: SenderIdCreate, *, actor_id=None, ip=None) -> SmsSenderId:
        if self._company_id is None:
            raise ValidationError("SMS sender IDs are managed within a company")
        # Per-tenant uniqueness (not global).
        if await self.sender_ids.get_by_value(data.sender_id) is not None:
            raise ConflictError("A sender ID with this value already exists")
        sender = await self.sender_ids.create(
            company_id=self._company_id,
            name=data.name,
            sender_id=data.sender_id,
            description=data.description,
            status=SenderStatus.ACTIVE,
            approval_status=SenderApprovalStatus.PENDING,
            is_default=False,
        )
        await self.audit.record(
            action="create", entity_type=_SENDER_ENTITY, entity_id=str(sender.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": sender.name, "sender_id": sender.sender_id},
        )
        await self.session.commit()
        await self.session.refresh(sender)
        return sender

    async def update_sender_id(self, sender_id, data: SenderIdUpdate, *, actor_id=None, ip=None) -> SmsSenderId:
        sender = await self.get_sender_id(sender_id)
        patch = data.model_dump(exclude_unset=True)
        if patch:
            await self.sender_ids.update(sender, **patch)
            await self.audit.record(
                action="update", entity_type=_SENDER_ENTITY, entity_id=str(sender.id),
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                new_values=patch,
            )
            await self.session.commit()
            await self.session.refresh(sender)
        return sender

    async def set_default_sender_id(self, sender_id, *, actor_id=None, ip=None):
        sender = await self.get_sender_id(sender_id)
        if sender.approval_status != SenderApprovalStatus.APPROVED:
            raise ValidationError("Only an approved sender ID can be set as default")
        await self.sender_ids.clear_default()
        sender.is_default = True
        await self.session.flush()
        await self.audit.record(
            action="set_default", entity_type=_SENDER_ENTITY, entity_id=str(sender.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
        )
        await self.session.commit()
        await self.session.refresh(sender)
        return sender

    async def activate_sender_id(self, sender_id, *, actor_id=None, ip=None):
        return await self._set_sender_status(sender_id, SenderStatus.ACTIVE, "activate", actor_id, ip)

    async def deactivate_sender_id(self, sender_id, *, actor_id=None, ip=None):
        return await self._set_sender_status(sender_id, SenderStatus.INACTIVE, "deactivate", actor_id, ip)

    async def _set_sender_status(self, sender_id, status: SenderStatus, action: str, actor_id, ip):
        sender = await self.get_sender_id(sender_id)
        sender.status = status
        await self.session.flush()
        await self.audit.record(
            action=action, entity_type=_SENDER_ENTITY, entity_id=str(sender.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
        )
        await self.session.commit()
        await self.session.refresh(sender)
        return sender

    # ----- super-admin review (cross-tenant) --------------------------------
    async def list_pending_sender_ids(self, *, search=None, offset: int = 0, limit: int = 20):
        return await self.sender_ids.list_pending_all_companies(
            search=search, offset=offset, limit=limit,
        )

    async def approve_sender_id(self, sender_id, *, reviewer_id=None, ip=None):
        sender = await self._get_for_review(sender_id)
        sender.approval_status = SenderApprovalStatus.APPROVED
        sender.rejection_reason = None
        sender.reviewed_by = reviewer_id
        sender.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.audit.record(
            action="approve", entity_type=_SENDER_ENTITY, entity_id=str(sender.id),
            actor_id=reviewer_id, company_id=sender.company_id, ip_address=ip,
        )
        await self.session.commit()
        await self.session.refresh(sender)
        return sender

    async def reject_sender_id(self, sender_id, reason: Optional[str], *, reviewer_id=None, ip=None):
        sender = await self._get_for_review(sender_id)
        sender.approval_status = SenderApprovalStatus.REJECTED
        sender.rejection_reason = reason
        sender.reviewed_by = reviewer_id
        sender.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.audit.record(
            action="reject", entity_type=_SENDER_ENTITY, entity_id=str(sender.id),
            actor_id=reviewer_id, company_id=sender.company_id, ip_address=ip,
            new_values={"reason": reason},
        )
        await self.session.commit()
        await self.session.refresh(sender)
        return sender

    async def _get_for_review(self, sender_id) -> SmsSenderId:
        # Super admins have no company scope; fetch across tenants.
        sender = await self.sender_ids.get_any_company(sender_id)
        if sender is None:
            raise NotFoundError("Sender ID not found")
        if sender.approval_status != SenderApprovalStatus.PENDING:
            raise ValidationError("Sender ID is not pending review")
        return sender

    # ===================================================================== #
    # Templates
    # ===================================================================== #
    async def list_templates(self, *, search=None, status=None, offset: int = 0, limit: int = 20):
        return await self.templates.search(
            search=search, status=status, offset=offset, limit=limit,
        )

    async def get_template(self, template_id) -> SmsTemplate:
        template = await self.templates.get_by_id(template_id)
        if template is None:
            raise NotFoundError("Template not found")
        return template

    async def create_template(self, data: TemplateCreate, *, actor_id=None, ip=None) -> SmsTemplate:
        if self._company_id is None:
            raise ValidationError("SMS templates are managed within a company")
        template = await self.templates.create(
            company_id=self._company_id,
            name=data.name,
            body=data.body,
            variables=extract_variables(data.body),
            status=data.status or SmsTemplateStatus.ACTIVE,
        )
        await self.audit.record(
            action="create", entity_type=_TEMPLATE_ENTITY, entity_id=str(template.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": template.name, "variables": template.variables},
        )
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def update_template(self, template_id, data: TemplateUpdate, *, actor_id=None, ip=None) -> SmsTemplate:
        template = await self.get_template(template_id)
        patch = data.model_dump(exclude_unset=True)
        if "body" in patch and patch["body"] is not None:
            patch["variables"] = extract_variables(patch["body"])
        if patch:
            await self.templates.update(template, **patch)
            await self.audit.record(
                action="update", entity_type=_TEMPLATE_ENTITY, entity_id=str(template.id),
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                new_values=patch,
            )
            await self.session.commit()
            await self.session.refresh(template)
        return template

    async def delete_template(self, template_id, *, actor_id=None, ip=None) -> None:
        template = await self.get_template(template_id)
        await self.templates.soft_delete(template)
        await self.audit.record(
            action="delete", entity_type=_TEMPLATE_ENTITY, entity_id=str(template.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
        )
        await self.session.commit()

    async def duplicate_template(self, template_id, *, actor_id=None, ip=None) -> SmsTemplate:
        source = await self.get_template(template_id)
        copy = await self.templates.create(
            company_id=self._company_id,
            name=f"{source.name} (Copy)",
            body=source.body,
            variables=list(source.variables),
            status=source.status,
        )
        await self.audit.record(
            action="duplicate", entity_type=_TEMPLATE_ENTITY, entity_id=str(copy.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"source_id": str(source.id)},
        )
        await self.session.commit()
        await self.session.refresh(copy)
        return copy

    @staticmethod
    def preview_template(data: TemplatePreviewRequest) -> dict:
        return {
            "variables": extract_variables(data.body),
            "body": render_template(data.body, data.values),
        }
