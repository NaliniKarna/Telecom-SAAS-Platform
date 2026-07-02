"""Contact CSV import service (C3).

Two-step flow:
  preview(csv_bytes) -> per-row validation + normalization + duplicate flags,
                        writing nothing;
  commit(rows, on_duplicate) -> bulk insert of valid, non-duplicate rows,
                                audited as a single contact/import event.

Reuses the Nepal normalizer and the contact repo's duplicate detection so import
behaves identically to single-contact create. Tenant isolation comes from the
repo's TenantContext.
"""
import csv
import io
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ContactNumberType, ContactStatus
from app.core.exceptions import ValidationError
from app.core.nepal_phone import normalize_nepal_number
from app.models.contact import Contact
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import (
    ImportCommitRequest,
    ImportPreviewResponse,
    ImportRowResult,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "contact"
_MAX_ROWS = 5000

# Accepted header spellings -> canonical field.
_HEADER_MAP = {
    "first_name": "first_name", "firstname": "first_name", "first name": "first_name",
    "last_name": "last_name", "lastname": "last_name", "last name": "last_name",
    "mobile": "mobile", "mobile_number": "mobile", "mobile number": "mobile",
    "phone": "mobile", "cell": "mobile",
    "landline": "landline", "landline_number": "landline", "landline number": "landline",
    "telephone": "landline",
    "email": "email", "email_address": "email", "e-mail": "email",
    "tags": "tags", "notes": "notes", "note": "notes",
    "status": "status",
}
_VALID_STATUSES = {s.value for s in ContactStatus}


class ContactImportService:
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

    # ---- parsing -------------------------------------------------------- #
    @staticmethod
    def _parse_tags(raw: str | None) -> list[str]:
        if not raw:
            return []
        parts = raw.replace(";", ",").split(",")
        seen, out = set(), []
        for p in (x.strip() for x in parts):
            if p and p.lower() not in seen:
                seen.add(p.lower())
                out.append(p)
        return out

    def _read_rows(self, csv_bytes: bytes) -> list[dict]:
        try:
            text = csv_bytes.decode("utf-8-sig")  # tolerate BOM
        except UnicodeDecodeError:
            raise ValidationError("CSV must be UTF-8 encoded")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise ValidationError("CSV appears to be empty")
        # Map headers; ignore unknown columns.
        canon = {}
        for h in reader.fieldnames:
            key = _HEADER_MAP.get((h or "").strip().lower())
            if key:
                canon[h] = key
        if "mobile" not in canon.values() and "email" not in canon.values():
            raise ValidationError(
                "CSV must include at least a mobile or email column"
            )
        rows = []
        for raw in reader:
            rows.append({canon[k]: (v or "").strip()
                         for k, v in raw.items() if k in canon})
            if len(rows) > _MAX_ROWS:
                raise ValidationError(f"CSV exceeds the {_MAX_ROWS}-row limit")
        return rows

    # ---- preview -------------------------------------------------------- #
    async def preview(self, csv_bytes: bytes) -> ImportPreviewResponse:
        if self._company_id is None:
            raise ValidationError("Contacts are managed within a company")
        rows = self._read_rows(csv_bytes)

        results: list[ImportRowResult] = []
        # Track within-file dupes (normalized mobile / lowercased email).
        seen_mobile: set[str] = set()
        seen_email: set[str] = set()
        v = inv = dup = 0

        for i, r in enumerate(rows, start=1):
            errors: list[str] = []
            m_raw, l_raw = r.get("mobile") or None, r.get("landline") or None
            email = (r.get("email") or None)
            m_e164 = l_e164 = None

            if m_raw:
                nm = normalize_nepal_number(m_raw)
                if not nm.is_valid:
                    errors.append(f"Invalid mobile: {m_raw!r}")
                else:
                    m_e164 = nm.e164
            if l_raw:
                nl = normalize_nepal_number(l_raw)
                if not nl.is_valid:
                    errors.append(f"Invalid landline: {l_raw!r}")
                else:
                    l_e164 = nl.e164
            if not m_raw and not email:
                errors.append("Row needs at least a mobile or email")

            status = (r.get("status") or "active").lower()
            if status not in _VALID_STATUSES:
                errors.append(f"Invalid status: {status!r}")

            row_status = "valid"
            if errors:
                row_status = "invalid"
                inv += 1
            else:
                # duplicate check: in-file first, then DB
                is_dup = (
                    (m_e164 and m_e164 in seen_mobile)
                    or (email and email.lower() in seen_email)
                )
                if not is_dup:
                    existing = await self.repo.find_duplicate(
                        mobile_e164=m_e164, email=email
                    )
                    is_dup = existing is not None
                if is_dup:
                    row_status = "duplicate"
                    dup += 1
                else:
                    v += 1
                    if m_e164:
                        seen_mobile.add(m_e164)
                    if email:
                        seen_email.add(email.lower())

            results.append(ImportRowResult(
                row_number=i, first_name=r.get("first_name") or None,
                last_name=r.get("last_name") or None,
                mobile=m_raw, mobile_e164=m_e164,
                landline=l_raw, landline_e164=l_e164,
                email=email, tags=self._parse_tags(r.get("tags")),
                notes=r.get("notes") or None,
                status=status if status in _VALID_STATUSES else "active",
                row_status=row_status, errors=errors,
            ))

        return ImportPreviewResponse(
            total=len(results), valid=v, invalid=inv, duplicate=dup, rows=results,
        )

    # ---- commit --------------------------------------------------------- #
    async def commit(
        self, req: ImportCommitRequest, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ):
        if self._company_id is None:
            raise ValidationError("Contacts are managed within a company")

        imported = skipped = failed = 0
        errors: list[str] = []
        batch_mobile: set[str] = set()
        batch_email: set[str] = set()

        for idx, row in enumerate(req.rows, start=1):
            try:
                m_e164 = l_e164 = None
                ntype = ContactNumberType.UNKNOWN
                if row.mobile:
                    nm = normalize_nepal_number(row.mobile)
                    if not nm.is_valid:
                        failed += 1
                        errors.append(f"Row {idx}: invalid mobile")
                        continue
                    m_e164, ntype = nm.e164, ContactNumberType.MOBILE
                if row.landline:
                    nl = normalize_nepal_number(row.landline)
                    if not nl.is_valid:
                        failed += 1
                        errors.append(f"Row {idx}: invalid landline")
                        continue
                    l_e164 = nl.e164
                    if ntype != ContactNumberType.MOBILE:
                        ntype = ContactNumberType.LANDLINE
                email = str(row.email) if row.email else None

                # duplicate check (DB + within this batch)
                dup_in_batch = (
                    (m_e164 and m_e164 in batch_mobile)
                    or (email and email.lower() in batch_email)
                )
                existing = (
                    None if dup_in_batch
                    else await self.repo.find_duplicate(mobile_e164=m_e164, email=email)
                )
                if dup_in_batch or existing is not None:
                    if req.on_duplicate == "skip":
                        skipped += 1
                        continue
                    # import_anyway falls through and inserts a new contact

                self.session.add(Contact(
                    company_id=self._company_id,
                    first_name=row.first_name, last_name=row.last_name,
                    mobile_raw=row.mobile, mobile_e164=m_e164,
                    landline_raw=row.landline, landline_e164=l_e164,
                    number_type=ntype, email=email,
                    tags=row.tags, notes=row.notes, status=row.status,
                ))
                imported += 1
                if m_e164:
                    batch_mobile.add(m_e164)
                if email:
                    batch_email.add(email.lower())
            except Exception as exc:  # noqa: BLE001 — per-row resilience
                failed += 1
                errors.append(f"Row {idx}: {exc}")

        if imported:
            await self.session.flush()
            await self.audit.record(
                action="import", entity_type=_ENTITY, entity_id="bulk",
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                new_values={"imported": imported, "skipped_duplicates": skipped,
                            "failed": failed, "on_duplicate": req.on_duplicate},
            )
            await self.session.commit()
        else:
            await self.session.rollback()

        return imported, skipped, failed, errors[:50]
