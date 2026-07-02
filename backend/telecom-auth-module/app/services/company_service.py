"""Company management use cases.

Owns transaction boundaries and business rules (slug uniqueness, status
transitions). Records an audit entry for every mutating action on the same
transaction. Raises domain exceptions only; the route layer maps to HTTP.
"""
import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CompanyStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyFilter, CompanyUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "company"


class CompanyService:
    def __init__(
        self,
        session: AsyncSession,
        repo: CompanyRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.companies = repo
        # Audit is optional so existing callers/tests keep working; the route
        # provider always supplies it.
        self.audit = audit or AuditService(session)

    # ----- reads ------------------------------------------------------------
    async def list_companies(
        self, *, offset: int, limit: int, filters: CompanyFilter | None = None
    ) -> tuple[Sequence[Company], int]:
        f = filters or CompanyFilter()
        return await self.companies.search(
            offset=offset,
            limit=limit,
            search=f.search,
            status=f.status,
            plan_id=f.plan_id,
            sort_by=f.sort_by,
            sort_dir=f.sort_dir,
        )

    async def get_company(self, company_id) -> Company:
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise NotFoundError("Company not found")
        return company

    # ----- mutations (each audited on the same transaction) -----------------
    async def create_company(
        self, data: CompanyCreate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> Company:
        if await self.companies.slug_exists(data.slug):
            raise ConflictError(f"A company with slug '{data.slug}' already exists")
        company = await self.companies.create(
            name=data.name,
            slug=data.slug,
            plan_id=data.plan_id,
            status=CompanyStatus.ACTIVE,
        )
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=company.id,
            actor_id=actor_id, company_id=company.id, ip_address=ip,
            new_values={"name": company.name, "slug": company.slug,
                        "plan_id": str(company.plan_id) if company.plan_id else None,},
        )
        await self.session.commit()
        await self.session.refresh(company)
        logger.info("company_created", extra={"company_id": str(company.id)})
        return company

    async def update_company(
        self, company_id, data: CompanyUpdate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> Company:
        company = await self.get_company(company_id)
        patch = data.model_dump(exclude_unset=True)
        if patch:
            before = {k: getattr(company, k) for k in patch}
            await self.companies.update(company, **patch)
            await self.audit.record(
                action="update", entity_type=_ENTITY, entity_id=company.id,
                actor_id=actor_id, company_id=company.id, ip_address=ip,
                old_values=before, new_values=patch,
            )
            await self.session.commit()
            await self.session.refresh(company)
        return company

    async def delete_company(
        self, company_id, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> None:
        company = await self.get_company(company_id)
        await self.companies.soft_delete(company)
        await self.audit.record(
            action="delete", entity_type=_ENTITY, entity_id=company_id,
            actor_id=actor_id, company_id=company_id, ip_address=ip,
        )
        await self.session.commit()
        logger.info("company_deleted", extra={"company_id": str(company_id)})

    async def set_status(
        self, company_id, status: CompanyStatus, *, action: str,
        actor_id: Optional[Any] = None, ip: Optional[str] = None,
    ) -> Company:
        company = await self.get_company(company_id)
        if company.status != status:
            before = company.status.value
            await self.companies.update(company, status=status)
            await self.audit.record(
                action=action, entity_type=_ENTITY, entity_id=company.id,
                actor_id=actor_id, company_id=company.id, ip_address=ip,
                old_values={"status": before},
                new_values={"status": status.value},
            )
            await self.session.commit()
            await self.session.refresh(company)
        return company

    async def activate_company(
        self, company_id, *, actor_id=None, ip=None
    ) -> Company:
        return await self.set_status(
            company_id, CompanyStatus.ACTIVE, action="activate",
            actor_id=actor_id, ip=ip,
        )

    async def deactivate_company(
        self, company_id, *, actor_id=None, ip=None
    ) -> Company:
        return await self.set_status(
            company_id, CompanyStatus.DEACTIVATED, action="deactivate",
            actor_id=actor_id, ip=ip,
        )

    async def suspend_company(
        self, company_id, *, actor_id=None, ip=None
    ) -> Company:
        # Temporary hold (billing/abuse). Distinct from deactivate so the audit
        # trail records why the account was turned off; restored via activate.
        return await self.set_status(
            company_id, CompanyStatus.SUSPENDED, action="suspend",
            actor_id=actor_id, ip=ip,
        )