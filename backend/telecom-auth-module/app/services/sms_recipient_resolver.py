"""Campaign recipient resolution layer.

Converts a campaign's source (a contact list, or an explicit set of individual
contacts) into a FROZEN recipient set:

  - only contacts with a usable mobile number (mobile_e164) are included,
  - phone numbers are de-duplicated (first occurrence wins),
  - each recipient row SNAPSHOTS the contact's phone + display name at resolve
    time, so later edits/deletes to the contact never alter campaign history,
  - contact_id is stored as a soft link (SET NULL on contact delete) for
    traceability, but the snapshot is the source of truth.

Resolution is tenant-safe: contacts and lists are loaded through tenant-scoped
repositories, so a campaign can only ever resolve its own company's contacts.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import SmsCampaignSource
from app.core.exceptions import ValidationError
from app.repositories.contact_list_repository import ContactListRepository
from app.repositories.contact_repository import ContactRepository


@dataclass
class ResolvedRecipient:
    contact_id: object | None
    phone_e164: str
    resolved_name: str | None


def _display_name(first: str | None, last: str | None) -> str | None:
    name = " ".join(p for p in (first, last) if p).strip()
    return name or None


class SmsRecipientResolver:
    def __init__(self, contacts: ContactRepository, lists: ContactListRepository):
        self.contacts = contacts
        self.lists = lists

    async def resolve(
        self, *, source_type: str, source_list_id=None, contact_ids: list | None = None,
    ) -> list[ResolvedRecipient]:
        if source_type == SmsCampaignSource.CONTACT_LIST.value:
            return await self._from_list(source_list_id)
        if source_type == SmsCampaignSource.CONTACTS.value:
            return await self._from_contacts(contact_ids or [])
        raise ValidationError(f"Unknown campaign source type: {source_type}")

    async def _from_list(self, list_id) -> list[ResolvedRecipient]:
        if list_id is None:
            raise ValidationError("A contact list is required for this source")
        contact_list = await self.lists.get_by_id(list_id)
        if contact_list is None:
            raise ValidationError("Contact list not found")
        members = await self.lists.list_members(list_id)
        return self._dedupe(contact for _membership, contact in members)

    async def _from_contacts(self, contact_ids: list) -> list[ResolvedRecipient]:
        if not contact_ids:
            raise ValidationError("At least one contact is required for this source")
        contacts = []
        for cid in contact_ids:
            c = await self.contacts.get_by_id(cid)  # tenant-scoped
            if c is not None:
                contacts.append(c)
        return self._dedupe(contacts)

    @staticmethod
    def _dedupe(contacts) -> list[ResolvedRecipient]:
        seen: set[str] = set()
        out: list[ResolvedRecipient] = []
        for c in contacts:
            phone = getattr(c, "mobile_e164", None)
            if not phone or phone in seen:
                continue
            seen.add(phone)
            out.append(ResolvedRecipient(
                contact_id=c.id,
                phone_e164=phone,
                resolved_name=_display_name(c.first_name, c.last_name),
            ))
        return out
