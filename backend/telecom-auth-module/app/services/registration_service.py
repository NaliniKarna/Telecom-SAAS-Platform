"""Public company self-registration + super-admin approval.

Flow:
  register_company  -> Company(PENDING_APPROVAL) + company_admin User(PENDING,
                       unverified) with a chosen password; email-verification
                       token issued.
  (user verifies email via the existing auth verify-email flow — marks the
   email verified but changes NO status: the company stays PENDING_APPROVAL.)
  approve           -> requires the admin's email verified; Company->ACTIVE and
                       admin User->ACTIVE. Login now succeeds (the existing
                       login gate blocks non-ACTIVE company/user, so this is the
                       single switch that grants access).
  reject            -> Company->REJECTED (admin stays inactive).

Reuses existing building blocks only: CompanyRepository, UserRepository
(create/get_role/set_role/email_exists), the email-verification token, and the
audit service. The super-admin company-creation and invite flows are untouched.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CompanyStatus, RoleName, UserStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import create_email_verification_token, hash_password
from app.models.company import Company
from app.models.user import User
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.registration import CompanyRegistrationRequest
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "company_registration"


class RegistrationService:
    def __init__(
        self,
        session: AsyncSession,
        company_repo: CompanyRepository | None = None,
        user_repo: UserRepository | None = None,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.companies = company_repo or CompanyRepository(session)
        # Unscoped user repo: registration + approval are platform-level (no
        # tenant context), same as the super-admin invite path.
        self.users = user_repo or UserRepository(session)
        self.audit = audit or AuditService(session)

    # ----- public registration ---------------------------------------------
    async def register_company(
        self, data: CompanyRegistrationRequest, *, ip: Optional[str] = None
    ) -> tuple[Company, User, str]:
        role = await self.users.get_role(RoleName.COMPANY_ADMIN.value)
        if role is None:
            raise ValidationError("company_admin role is not configured")

        # Email must be globally unique (same rule as invite/create).
        if await self.users.email_exists(data.admin_email):
            raise ConflictError(
                "An account with that email already exists. Try signing in instead."
            )

        slug = await self._unique_slug(data.company_name)

        company = await self.companies.create(
            name=data.company_name,
            slug=slug,
            status=CompanyStatus.PENDING_APPROVAL,
            contact_email=data.admin_email,
            contact_phone=data.contact_phone,
            metadata_={"self_registered": True},
        )

        user = await self.users.create(
            company_id=company.id,
            email=data.admin_email,
            hashed_password=hash_password(data.password),
            first_name=data.admin_first_name,
            last_name=data.admin_last_name,
            status=UserStatus.PENDING,
            is_email_verified=False,
        )
        await self.users.set_role(user, role, assigned_by=None)

        # Record the admin on the company so approval resolves it unambiguously.
        company.metadata_ = {**(company.metadata_ or {}),
                             "self_registered": True,
                             "admin_user_id": str(user.id)}

        token = create_email_verification_token(str(user.id))

        await self.audit.record(
            action="register", entity_type=_ENTITY, entity_id=company.id,
            actor_id=None, company_id=company.id, ip_address=ip,
            new_values={"company": company.name, "slug": slug,
                        "admin_email": str(data.admin_email)},
        )
        await self.session.commit()
        await self.session.refresh(company)
        await self.session.refresh(user)
        logger.info("company_registered", extra={"company_id": str(company.id)})
        return company, user, token

    # ----- super-admin review ----------------------------------------------
    async def list_pending(self) -> list[tuple[Company, Optional[User]]]:
        companies = (await self.session.execute(
            select(Company)
            .where(
                Company.status == CompanyStatus.PENDING_APPROVAL,
                Company.deleted_at.is_(None),
            )
            .order_by(Company.created_at.asc())
        )).scalars().all()
        out: list[tuple[Company, Optional[User]]] = []
        for c in companies:
            out.append((c, await self._admin_of(c)))
        return out

    async def approve(
        self, company_id, *, reviewer_id: Any, ip: Optional[str] = None
    ) -> Company:
        company = await self._get_pending(company_id)
        admin = await self._admin_of(company)
        if admin is None:
            raise ValidationError("No company admin is associated with this registration")
        if not admin.is_email_verified:
            raise ValidationError(
                "The company admin must verify their email before approval"
            )

        company.status = CompanyStatus.ACTIVE
        admin.status = UserStatus.ACTIVE
        await self.audit.record(
            action="approve", entity_type=_ENTITY, entity_id=company.id,
            actor_id=reviewer_id, company_id=company.id, ip_address=ip,
            new_values={"status": CompanyStatus.ACTIVE.value,
                        "admin_user_id": str(admin.id)},
        )
        await self.session.commit()
        await self.session.refresh(company)
        logger.info("company_registration_approved",
                    extra={"company_id": str(company.id)})
        return company

    async def reject(
        self, company_id, *, reviewer_id: Any, reason: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> Company:
        company = await self._get_pending(company_id)
        company.status = CompanyStatus.REJECTED
        if reason:
            company.metadata_ = {**(company.metadata_ or {}),
                                 "rejection_reason": reason}
        await self.audit.record(
            action="reject", entity_type=_ENTITY, entity_id=company.id,
            actor_id=reviewer_id, company_id=company.id, ip_address=ip,
            new_values={"status": CompanyStatus.REJECTED.value,
                        "reason": reason} if reason else
                       {"status": CompanyStatus.REJECTED.value},
        )
        await self.session.commit()
        await self.session.refresh(company)
        return company

    # ----- helpers ----------------------------------------------------------
    async def _get_pending(self, company_id) -> Company:
        company = await self.session.get(Company, company_id)
        if company is None or company.deleted_at is not None:
            raise NotFoundError("Registration not found")
        if company.status != CompanyStatus.PENDING_APPROVAL:
            raise ConflictError("This registration has already been reviewed")
        return company

    async def _admin_of(self, company: Company) -> Optional[User]:
        """Resolve the registering admin: prefer the id recorded at registration,
        else fall back to the earliest company_admin in the company."""
        admin_id = (company.metadata_ or {}).get("admin_user_id")
        if admin_id:
            user = await self.users.get_by_id_unscoped(admin_id)
            if user is not None:
                return user
        row = (await self.session.execute(
            select(User)
            .where(User.company_id == company.id, User.deleted_at.is_(None))
            .order_by(User.created_at.asc())
        )).scalars().first()
        return row

    async def _unique_slug(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "company"
        slug = base
        while await self.companies.slug_exists(slug):
            slug = f"{base}-{secrets.token_hex(3)}"[:100]
        return slug
