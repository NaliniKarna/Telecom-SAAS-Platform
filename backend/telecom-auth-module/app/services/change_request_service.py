"""Company change-request service (approval workflow).

Gated company-settings fields (name, contact_email, contact_phone) don't change
the live company row directly; a company admin's edit creates a PENDING
CompanyChangeRequest capturing an old->new diff. A super admin then approves
(values are copied onto the live company + audited) or rejects (no change).

At most one PENDING request per company (DB partial-unique index + a guard here
with a friendly error).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ChangeRequestStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.company import Company
from app.models.company_change_request import CompanyChangeRequest
from app.repositories.company_repository import CompanyRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Fields that require super-admin approval before taking effect.
GATED_FIELDS = ("name", "contact_email", "contact_phone")
_ENTITY = "company_change_request"


class ChangeRequestService:
    def __init__(
        self,
        session: AsyncSession,
        repo: CompanyRepository | None = None,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.companies = repo or CompanyRepository(session)
        self.audit = audit or AuditService(session)

    async def create_request(
        self, company: Company, changes: dict[str, Any], *,
        actor_id: Optional[Any] = None, ip: Optional[str] = None,
    ) -> CompanyChangeRequest:
        """changes: {field: new_value} for GATED fields only. Builds an old->new
        diff, skipping no-op fields. Raises ConflictError if one is pending."""
        diff = {}
        for field, new in changes.items():
            if field not in GATED_FIELDS:
                continue
            old = getattr(company, field)
            if (old or None) == (new or None):
                continue  # no actual change
            diff[field] = {"old": _s(old), "new": _s(new)}
        if not diff:
            raise ValidationError("No changes to submit for approval")

        if await self._pending_for(company.id) is not None:
            raise ConflictError(
                "A change request is already pending approval for this company"
            )

        req = CompanyChangeRequest(
            company_id=company.id,
            requested_by=actor_id,
            status=ChangeRequestStatus.PENDING,
            changes=diff,
        )
        self.session.add(req)
        await self.audit.record(
            action="submit", entity_type=_ENTITY, entity_id=str(company.id),
            actor_id=actor_id, company_id=company.id, ip_address=ip,
            new_values=diff,
        )
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def pending_for_company(self, company_id) -> CompanyChangeRequest | None:
        return await self._pending_for(company_id)

    async def list_pending(self) -> list[CompanyChangeRequest]:
        rows = (await self.session.execute(
            select(CompanyChangeRequest)
            .where(CompanyChangeRequest.status == ChangeRequestStatus.PENDING)
            .order_by(CompanyChangeRequest.created_at.asc())
        )).scalars().all()
        return list(rows)

    async def approve(
        self, request_id, *, reviewer_id: Any, ip: Optional[str] = None,
    ) -> CompanyChangeRequest:
        req = await self._get_pending(request_id)
        company = await self.session.get(Company, req.company_id)
        if company is None or company.deleted_at is not None:
            raise NotFoundError("Company not found")

        applied = {}
        for field, diff in req.changes.items():
            if field in GATED_FIELDS:
                setattr(company, field, diff.get("new"))
                applied[field] = diff
        req.status = ChangeRequestStatus.APPROVED
        req.reviewed_by = reviewer_id
        req.reviewed_at = datetime.now(timezone.utc)
        await self.audit.record(
            action="approve", entity_type=_ENTITY, entity_id=str(company.id),
            actor_id=reviewer_id, company_id=company.id, ip_address=ip,
            new_values=applied,
        )
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def reject(
        self, request_id, *, reviewer_id: Any, reason: str | None = None,
        ip: Optional[str] = None,
    ) -> CompanyChangeRequest:
        req = await self._get_pending(request_id)
        req.status = ChangeRequestStatus.REJECTED
        req.reviewed_by = reviewer_id
        req.reviewed_at = datetime.now(timezone.utc)
        req.decision_reason = reason
        await self.audit.record(
            action="reject", entity_type=_ENTITY, entity_id=str(req.company_id),
            actor_id=reviewer_id, company_id=req.company_id, ip_address=ip,
            new_values={"reason": reason} if reason else None,
        )
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def _pending_for(self, company_id) -> CompanyChangeRequest | None:
        return (await self.session.execute(
            select(CompanyChangeRequest).where(
                CompanyChangeRequest.company_id == company_id,
                CompanyChangeRequest.status == ChangeRequestStatus.PENDING,
            )
        )).scalars().first()

    async def _get_pending(self, request_id) -> CompanyChangeRequest:
        req = await self.session.get(CompanyChangeRequest, request_id)
        if req is None:
            raise NotFoundError("Change request not found")
        if req.status != ChangeRequestStatus.PENDING:
            raise ConflictError("This change request has already been reviewed")
        return req


def _s(v) -> str | None:
    return None if v is None else str(v)
