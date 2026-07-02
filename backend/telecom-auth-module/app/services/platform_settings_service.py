"""Platform settings service.

Manages the single platform_settings row. get_settings returns it (creating the
singleton on the fly if somehow absent); update_settings patches provided fields,
validates the default_plan_id reference, and records an audit entry.
"""
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.platform_settings import SETTINGS_SINGLETON_ID, PlatformSettings
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.platform_settings import PlatformSettingsUpdate
from app.services.audit_service import AuditService

_ENTITY = "platform_settings"


class PlatformSettingsService:
    def __init__(self, session: AsyncSession, audit: AuditService | None = None):
        self.session = session
        self.audit = audit or AuditService(session)

    async def get_settings(self) -> PlatformSettings:
        row = await self.session.get(PlatformSettings, SETTINGS_SINGLETON_ID)
        if row is None:
            # Self-heal: create the singleton with model defaults.
            row = PlatformSettings(id=SETTINGS_SINGLETON_ID)
            self.session.add(row)
            await self.session.commit()
            await self.session.refresh(row)
        return row

    async def update_settings(
        self, data: PlatformSettingsUpdate, *,
        actor_id: Optional[Any] = None, ip: Optional[str] = None,
    ) -> PlatformSettings:
        row = await self.get_settings()
        patch = data.model_dump(exclude_unset=True)

        # Validate default_plan_id references an existing, active plan.
        if patch.get("default_plan_id") is not None:
            plan = await self.session.get(
                SubscriptionPlan, patch["default_plan_id"]
            )
            if plan is None or plan.deleted_at is not None:
                raise ValidationError("default_plan_id does not reference a valid plan")

        if patch:
            before = {k: getattr(row, k) for k in patch}
            for k, v in patch.items():
                setattr(row, k, v)
            await self.session.flush()
            await self.audit.record(
                action="update", entity_type=_ENTITY, entity_id=str(row.id),
                actor_id=actor_id, ip_address=ip,
                old_values=_jsonable(before), new_values=_jsonable(patch),
            )
            await self.session.commit()
            await self.session.refresh(row)
        return row


def _jsonable(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        out[k] = v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
    return out
