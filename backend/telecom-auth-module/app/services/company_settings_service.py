"""Company Settings service (Company Admin, self-scoped).

A company admin edits ONLY their own company. The acting company_id is passed
in from the authenticated token by the route layer and used directly — there is
no client-supplied company id anywhere in this flow, so cross-tenant edits are
impossible by construction.

Only profile/branding fields are editable here (name, contact, address,
timezone, logo). Plan, limits, feature entitlements, and status are
platform-controlled and never mutated by this service.
"""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanySettingsUpdate
from app.services.audit_service import AuditService
from app.services.change_request_service import (
    ChangeRequestService,
    GATED_FIELDS,
)

logger = logging.getLogger(__name__)

_ENTITY = "company_settings"
# Fields a company admin may edit. GATED_FIELDS (name, contact_email,
# contact_phone) require super-admin approval; the rest save immediately.
_EDITABLE = (
    "name", "contact_email", "contact_phone", "address", "timezone", "logo_url",
)
_IMMEDIATE = tuple(f for f in _EDITABLE if f not in GATED_FIELDS)


class CompanySettingsService:
    def __init__(
        self,
        session: AsyncSession,
        repo: CompanyRepository,
        audit: AuditService | None = None,
        change_requests: ChangeRequestService | None = None,
    ):
        self.session = session
        self.companies = repo
        self.audit = audit or AuditService(session)
        self.change_requests = change_requests or ChangeRequestService(
            session, repo, self.audit
        )

    async def get_own(self, company_id) -> Company:
        if company_id is None:
            # A super admin has no company; this endpoint is tenant-scoped.
            raise NotFoundError("No company associated with this account")
        company = await self.companies.get_by_id(company_id)
        if company is None or company.deleted_at is not None:
            raise NotFoundError("Company not found")
        return company

    async def update_own(
        self, company_id, data: CompanySettingsUpdate, *,
        actor_id: Optional[Any] = None, ip: Optional[str] = None,
    ):
        """Returns (company, immediate_applied, pending_request).

        Immediate fields (address/timezone/logo) save now and are audited.
        Gated fields (name/contact_email/contact_phone) become a pending change
        request that takes effect only on super-admin approval.
        """
        company = await self.get_own(company_id)
        patch = {
            k: v for k, v in data.model_dump(exclude_unset=True).items()
            if k in _EDITABLE
        }

        immediate = {k: v for k, v in patch.items() if k in _IMMEDIATE}
        gated = {k: v for k, v in patch.items() if k in GATED_FIELDS}

        applied: list[str] = []
        if immediate:
            before = {k: getattr(company, k) for k in immediate}
            await self.companies.update(company, **immediate)
            await self.audit.record(
                action="update", entity_type=_ENTITY, entity_id=str(company.id),
                actor_id=actor_id, company_id=company.id, ip_address=ip,
                old_values=_jsonable(before), new_values=_jsonable(immediate),
            )
            await self.session.commit()
            await self.session.refresh(company)
            applied = list(immediate.keys())

        pending = None
        if gated:
            pending = await self.change_requests.create_request(
                company, gated, actor_id=actor_id, ip=ip
            )
        return company, applied, pending

    async def set_logo(
        self, company_id, logo_url: str, *,
        actor_id: Optional[Any] = None, ip: Optional[str] = None,
    ) -> Company:
        company = await self.get_own(company_id)
        old = company.logo_url
        await self.companies.update(company, logo_url=logo_url)
        await self.audit.record(
            action="update_logo", entity_type=_ENTITY, entity_id=str(company.id),
            actor_id=actor_id, company_id=company.id, ip_address=ip,
            old_values={"logo_url": old}, new_values={"logo_url": logo_url},
        )
        await self.session.commit()
        await self.session.refresh(company)
        return company


def _jsonable(d: dict) -> dict:
    return {
        k: (v if isinstance(v, (str, int, float, bool, type(None))) else str(v))
        for k, v in d.items()
    }
