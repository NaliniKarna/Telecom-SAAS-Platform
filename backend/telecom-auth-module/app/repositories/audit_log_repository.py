"""Audit log data access (read side).

Append-only table; this repository only queries. Joins actor (user) and company
for display names, supports the full filter set (company / user / action /
module / date range / free-text), pagination, and sorting by time. Also exposes
distinct actions and modules for filter dropdowns.

Designed to scale to future event sources (Company Admin, SMS, Voice, API keys,
FreePBX): those just write new entity_type/action values via AuditService, and
they show up here with no query changes.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.user import User


class AuditLogRepository:
    def __init__(self, session):
        self.session = session

    async def search(
        self, *, offset: int, limit: int,
        search: Optional[str] = None,
        company_id=None, actor_id=None,
        action: Optional[str] = None, entity_type: Optional[str] = None,
        date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
        sort_dir: str = "desc",
    ):
        """Returns (rows, total). Each row is a tuple
        (AuditLog, actor_email, actor_first, actor_last, company_name)."""
        actor = aliased(User)
        comp = aliased(Company)

        base = (
            select(
                AuditLog,
                actor.email.label("actor_email"),
                actor.first_name.label("actor_first"),
                actor.last_name.label("actor_last"),
                comp.name.label("company_name"),
            )
            .select_from(AuditLog)
            .outerjoin(actor, AuditLog.actor_id == actor.id)
            .outerjoin(comp, AuditLog.company_id == comp.id)
        )

        conds = []
        if company_id is not None:
            conds.append(AuditLog.company_id == company_id)
        if actor_id is not None:
            conds.append(AuditLog.actor_id == actor_id)
        if action:
            conds.append(AuditLog.action == action)
        if entity_type:
            conds.append(AuditLog.entity_type == entity_type)
        if date_from is not None:
            conds.append(AuditLog.created_at >= date_from)
        if date_to is not None:
            conds.append(AuditLog.created_at <= date_to)
        if search:
            term = f"%{search.lower()}%"
            conds.append(
                func.lower(AuditLog.action).like(term)
                | func.lower(AuditLog.entity_type).like(term)
                | func.lower(func.coalesce(AuditLog.description, "")).like(term)
                | func.lower(func.coalesce(AuditLog.entity_id, "")).like(term)
            )
        for c in conds:
            base = base.where(c)

        # total over the same filter set
        count_stmt = select(func.count()).select_from(AuditLog)
        for c in conds:
            count_stmt = count_stmt.where(c)
        total = (await self.session.execute(count_stmt)).scalar_one()

        order = AuditLog.id.asc() if sort_dir == "asc" else AuditLog.id.desc()
        base = base.order_by(order).offset(offset).limit(limit)
        rows = (await self.session.execute(base)).all()
        return rows, total

    async def distinct_actions(self) -> list[str]:
        stmt = select(AuditLog.action).distinct().order_by(AuditLog.action)
        return [r[0] for r in (await self.session.execute(stmt)).all()]

    async def distinct_modules(self) -> list[str]:
        stmt = (
            select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
        )
        return [r[0] for r in (await self.session.execute(stmt)).all()]
