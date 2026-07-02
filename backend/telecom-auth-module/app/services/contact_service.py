"""Contact service — company-scoped, tenant-isolated via the repo's ctx.

Applies Nepal E.164 normalization on save (storing raw + normalized + derived
number_type), detects duplicates by normalized mobile / email, and audits
create/update/delete.
"""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ContactNumberType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.nepal_phone import normalize_nepal_number
from app.models.contact import Contact
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "contact"


class ContactService:
    def __init__(
        self, session: AsyncSession, repo: ContactRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.repo = repo
        self.audit = audit or AuditService(session)

    @property
    def _company_id(self):
        return self.repo.ctx.company_id if self.repo.ctx else None

    async def list_contacts(self, flt, *, offset: int, limit: int):
        return await self.repo.search(
            search=flt.search, status=flt.status, tag=flt.tag,
            offset=offset, limit=limit,
        )

    async def get_contact(self, contact_id) -> Contact:
        c = await self.repo.get_by_id(contact_id)
        if c is None:
            raise NotFoundError("Contact not found")
        return c

    @staticmethod
    def _normalize(mobile: str | None, landline: str | None):
        """Returns (mobile_e164, landline_e164, number_type). Raises on a number
        that was provided but can't be validated."""
        m_e164 = l_e164 = None
        ntype = ContactNumberType.UNKNOWN
        if mobile and mobile.strip():
            r = normalize_nepal_number(mobile)
            if not r.is_valid:
                raise ValidationError(f"Invalid mobile number: {mobile!r}")
            m_e164, ntype = r.e164, ContactNumberType.MOBILE
        if landline and landline.strip():
            r = normalize_nepal_number(landline)
            if not r.is_valid:
                raise ValidationError(f"Invalid landline number: {landline!r}")
            l_e164 = r.e164
            if ntype != ContactNumberType.MOBILE:
                ntype = ContactNumberType.LANDLINE
        return m_e164, l_e164, ntype

    async def create_contact(
        self, data: ContactCreate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> Contact:
        if self._company_id is None:
            raise ValidationError("Contacts are managed within a company")
        m_e164, l_e164, ntype = self._normalize(data.mobile, data.landline)
        email = str(data.email) if data.email else None

        dup = await self.repo.find_duplicate(mobile_e164=m_e164, email=email)
        if dup is not None:
            raise ConflictError(
                "A contact with this mobile number or email already exists"
            )

        contact = await self.repo.create(
            company_id=self._company_id,
            first_name=data.first_name, last_name=data.last_name,
            mobile_raw=data.mobile, mobile_e164=m_e164,
            landline_raw=data.landline, landline_e164=l_e164,
            number_type=ntype, email=email, tags=data.tags,
            notes=data.notes, status=data.status,
        )
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=str(contact.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": _name(contact), "mobile_e164": m_e164,
                        "email": email, "status": contact.status.value},
        )
        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def update_contact(
        self, contact_id, data: ContactUpdate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> Contact:
        contact = await self.get_contact(contact_id)
        patch = data.model_dump(exclude_unset=True)
        before = {}

        # Re-normalize if either number field is being set.
        if "mobile" in patch or "landline" in patch:
            new_mobile = patch.get("mobile", contact.mobile_raw)
            new_landline = patch.get("landline", contact.landline_raw)
            m_e164, l_e164, ntype = self._normalize(new_mobile, new_landline)
            dup = await self.repo.find_duplicate(
                mobile_e164=m_e164, email=None, exclude_id=contact.id
            )
            if dup is not None:
                raise ConflictError("Another contact already has this mobile number")
            before["mobile_e164"] = contact.mobile_e164
            contact.mobile_raw, contact.mobile_e164 = new_mobile, m_e164
            contact.landline_raw, contact.landline_e164 = new_landline, l_e164
            contact.number_type = ntype
            patch.pop("mobile", None)
            patch.pop("landline", None)

        if "email" in patch:
            email = str(patch["email"]) if patch["email"] else None
            dup = await self.repo.find_duplicate(
                mobile_e164=None, email=email, exclude_id=contact.id
            )
            if dup is not None:
                raise ConflictError("Another contact already has this email")
            before["email"] = contact.email
            contact.email = email
            patch.pop("email")

        for k, v in patch.items():
            before[k] = _s(getattr(contact, k))
            setattr(contact, k, v)

        await self.session.flush()
        await self.audit.record(
            action="update", entity_type=_ENTITY, entity_id=str(contact.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            old_values=before,
            new_values={k: _s(getattr(contact, k)) for k in before},
        )
        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def delete_contact(
        self, contact_id, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> None:
        contact = await self.get_contact(contact_id)
        await self.repo.soft_delete(contact)
        await self.audit.record(
            action="delete", entity_type=_ENTITY, entity_id=str(contact.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            old_values={"name": _name(contact), "mobile_e164": contact.mobile_e164},
        )
        await self.session.commit()


def _name(c: Contact) -> str:
    return " ".join(filter(None, [c.first_name, c.last_name])) or "(no name)"


def _s(v) -> Any:
    return v.value if hasattr(v, "value") else v
